"""
requester_demo.py — Demo script that plays the Requester role against the
live ARC provider agent (provider.py). This is what you record for the
hackathon's demo video: it negotiates a real order, pays it on-chain in
USDC, waits for the delivered prediction, and locally checks the
prediction against the puzzle's known answer.

Run (after provider.py is online and this agent's wallet has USDC):
    export CROO_API_URL="https://api.croo.network"
    export CROO_WS_URL="wss://api.croo.network/ws"
    export CROO_SDK_KEY="croo_sk_...requester_key..."
    export CROO_TARGET_SERVICE_ID="<the provider's service id from the Dashboard>"
    python -m croo_arc_agent.requester_demo
"""

from __future__ import annotations

import asyncio
import json
import logging
import pathlib

from croo import AgentClient, DeliverableType, Event, EventType, NegotiateOrderRequest

from .config import load_requester_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("arc-requester-demo")

SAMPLE_TASK_PATH = pathlib.Path(__file__).resolve().parent.parent / "examples" / "sample_task.json"


async def main() -> None:
    config = load_requester_config()
    client = AgentClient(config.croo_config, config.sdk_key)

    sample = json.loads(SAMPLE_TASK_PATH.read_text())
    task = sample["task"]
    expected = sample.get("expected_test_output")

    stream = await client.connect_websocket()
    done = asyncio.Event()

    def on_order_created(e: Event) -> None:
        asyncio.create_task(_pay(e))

    async def _pay(e: Event) -> None:
        logger.info("order created order_id=%s -> paying", e.order_id)
        try:
            result = await client.pay_order(e.order_id)
            logger.info("payment confirmed tx_hash=%s", result.tx_hash)
        except Exception as err:
            logger.error("payment failed: %s", err)
            done.set()

    def on_negotiation_rejected(e: Event) -> None:
        logger.error("negotiation rejected by provider: %s", e.reason)
        done.set()

    def on_order_completed(e: Event) -> None:
        asyncio.create_task(_collect(e))

    async def _collect(e: Event) -> None:
        logger.info("order completed order_id=%s -> fetching delivery", e.order_id)
        delivery = await client.get_delivery(e.order_id)
        if delivery.deliverable_type == DeliverableType.SCHEMA:
            payload = json.loads(delivery.deliverable_schema)
        else:
            payload = {"raw_text": delivery.deliverable_text}

        print("\n========== DELIVERY RECEIVED ==========")
        print(json.dumps(payload, indent=2))

        if expected is not None and "predictions" in payload:
            is_correct = payload["predictions"] == expected
            verdict = "CORRECT ✅" if is_correct else "INCORRECT ❌"
            print(f"\nLocal verification against known answer: {verdict}")
        print("=========================================\n")

        done.set()

    stream.on(EventType.ORDER_CREATED, on_order_created)
    stream.on(EventType.ORDER_COMPLETED, on_order_completed)
    stream.on(EventType.NEGOTIATION_REJECTED, on_negotiation_rejected)
    stream.on(EventType.NEGOTIATION_EXPIRED, on_negotiation_rejected)
    stream.on(EventType.ORDER_REJECTED, lambda e: (logger.error("order rejected: %s", e.reason), done.set()))
    stream.on(EventType.ORDER_EXPIRED, lambda e: (logger.error("order expired"), done.set()))

    logger.info("negotiating order for service_id=%s", config.service_id)
    negotiation = await client.negotiate_order(
        NegotiateOrderRequest(
            service_id=config.service_id,
            requirements=json.dumps(task),
        )
    )
    logger.info("negotiation started negotiation_id=%s", negotiation.negotiation_id)

    await done.wait()
    await stream.close()
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
