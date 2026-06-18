"""
provider.py — CAP Provider Agent for the "ARC Abstract Reasoning Solver" service.

Role in the order lifecycle (see https://docs.croo.network):

    Requester                          Provider (this script)
        |  negotiate_order()  -------------->|
        |                                     |-- validate task JSON
        |                                     |-- accept_negotiation()
        |<-- [ws] order_created --------------|
        |  pay_order()                        |
        |                                     |<-- [ws] order_paid
        |                                     |-- solve_task()
        |                                     |-- deliver_order()
        |<-- [ws] order_completed ------------|
        |  get_delivery()                     |

Run:
    export CROO_API_URL="https://api.croo.network"
    export CROO_WS_URL="wss://api.croo.network/ws"
    export CROO_SDK_KEY="croo_sk_...provider_key..."
    python -m croo_arc_agent.provider

The requirements JSON a customer sends when negotiating must look like:

    {
      "train": [{"input": [[...]], "output": [[...]]}, ...],
      "test":  [{"input": [[...]]}]
    }

The deliverable returned is DeliverableType.SCHEMA, a JSON document:

    {
      "predictions": [[[...]]],
      "strategy_used": "flip_horizontal",
      "confidence": 0.97,
      "reasoning_hash": "sha256:...",
      "notes": "..."
    }
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal

from croo import (
    AgentClient,
    DeliverableType,
    DeliverOrderRequest,
    Event,
    EventType,
)

from .config import load_provider_config
from .solver import solve_task

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("arc-provider")


class ArcProviderAgent:
    """Wraps an AgentClient with order-handling logic for the ARC solver service."""

    def __init__(self, client: AgentClient) -> None:
        self.client = client
        # negotiation_id -> parsed task, kept only until the order is created
        self._tasks_by_negotiation: dict[str, dict] = {}
        # order_id -> parsed task, kept until delivered
        self._tasks_by_order: dict[str, dict] = {}
        self.orders_completed = 0
        self.orders_rejected = 0

    # ---- event handlers -------------------------------------------------

    def on_negotiation_created(self, e: Event) -> None:
        asyncio.create_task(self._handle_negotiation_created(e))

    async def _handle_negotiation_created(self, e: Event) -> None:
        logger.info("negotiation received negotiation_id=%s", e.negotiation_id)
        try:
            negotiation = await self.client.get_negotiation(e.negotiation_id)
            task = json.loads(negotiation.requirements)
            _validate_task_or_raise(task)
        except Exception as err:
            self.orders_rejected += 1
            logger.warning("rejecting negotiation %s: invalid task (%s)", e.negotiation_id, err)
            await self.client.reject_negotiation(
                e.negotiation_id, f"invalid ARC task schema: {err}"
            )
            return

        try:
            result = await self.client.accept_negotiation(e.negotiation_id)
        except Exception as err:
            logger.error("accept_negotiation failed for %s: %s", e.negotiation_id, err)
            return

        self._tasks_by_order[result.order.order_id] = task
        logger.info(
            "negotiation accepted negotiation_id=%s order_id=%s",
            e.negotiation_id, result.order.order_id,
        )

    def on_order_paid(self, e: Event) -> None:
        asyncio.create_task(self._handle_order_paid(e))

    async def _handle_order_paid(self, e: Event) -> None:
        logger.info("order paid, solving order_id=%s", e.order_id)
        task = self._tasks_by_order.pop(e.order_id, None)

        # Defensive fallback: if this provider process restarted between
        # accept and pay, re-fetch the task from the order's negotiation
        # instead of failing the order.
        if task is None:
            try:
                order = await self.client.get_order(e.order_id)
                negotiation = await self.client.get_negotiation(order.negotiation_id)
                task = json.loads(negotiation.requirements)
            except Exception as err:
                logger.error("could not recover task for order %s: %s", e.order_id, err)
                await self.client.reject_order(e.order_id, f"internal error: {err}")
                return

        try:
            result = solve_task(task)
        except Exception as err:
            logger.error("solver failed for order %s: %s", e.order_id, err)
            await self.client.reject_order(e.order_id, f"solver error: {err}")
            return

        deliverable = {
            "predictions": result.predictions,
            "strategy_used": result.strategy_used,
            "confidence": result.confidence,
            "reasoning_hash": result.reasoning_hash,
            "notes": result.notes,
        }

        try:
            await self.client.deliver_order(
                e.order_id,
                DeliverOrderRequest(
                    deliverable_type=DeliverableType.SCHEMA,
                    deliverable_schema=json.dumps(deliverable),
                ),
            )
            self.orders_completed += 1
            logger.info(
                "order delivered order_id=%s strategy=%s confidence=%.2f",
                e.order_id, result.strategy_used, result.confidence,
            )
        except Exception as err:
            logger.error("deliver_order failed for %s: %s", e.order_id, err)

    def on_order_completed(self, e: Event) -> None:
        logger.info("order completed & settled order_id=%s", e.order_id)

    def on_negotiation_rejected_or_expired(self, e: Event) -> None:
        logger.info("negotiation closed without an order negotiation_id=%s type=%s", e.negotiation_id, e.type)

    def on_order_problem(self, e: Event) -> None:
        logger.warning("order problem order_id=%s type=%s reason=%s", e.order_id, e.type, e.reason)


def _validate_task_or_raise(task: dict) -> None:
    if not isinstance(task, dict):
        raise ValueError("requirements must be a JSON object")
    if "train" not in task or "test" not in task:
        raise ValueError("missing 'train' or 'test' key")
    if not isinstance(task["train"], list) or not task["train"]:
        raise ValueError("'train' must be a non-empty list")
    if not isinstance(task["test"], list) or not task["test"]:
        raise ValueError("'test' must be a non-empty list")


async def main() -> None:
    config = load_provider_config()
    client = AgentClient(config.croo_config, config.sdk_key)
    agent = ArcProviderAgent(client)

    stream = await client.connect_websocket()
    stream.on(EventType.NEGOTIATION_CREATED, agent.on_negotiation_created)
    stream.on(EventType.ORDER_PAID, agent.on_order_paid)
    stream.on(EventType.ORDER_COMPLETED, agent.on_order_completed)
    stream.on(EventType.NEGOTIATION_REJECTED, agent.on_negotiation_rejected_or_expired)
    stream.on(EventType.NEGOTIATION_EXPIRED, agent.on_negotiation_rejected_or_expired)
    stream.on(EventType.ORDER_REJECTED, agent.on_order_problem)
    stream.on(EventType.ORDER_EXPIRED, agent.on_order_problem)

    logger.info("ARC provider agent online — waiting for orders...")

    stop = asyncio.Event()
    loop = asyncio.get_event_loop()
    try:
        loop.add_signal_handler(signal.SIGINT, stop.set)
        loop.add_signal_handler(signal.SIGTERM, stop.set)
    except NotImplementedError:
        # add_signal_handler isn't available on Windows event loops;
        # Ctrl+C will still raise KeyboardInterrupt and exit the process.
        pass

    await stop.wait()

    logger.info(
        "shutting down — orders_completed=%d orders_rejected=%d",
        agent.orders_completed, agent.orders_rejected,
    )
    await stream.close()
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
