# ARC Reasoning Agent — a paid, callable CAP agent for abstract grid reasoning

A CROO Agent Protocol (CAP) **Provider** agent that sells one narrow, well-defined
capability — solving ARC-AGI-style abstract grid-reasoning puzzles — as an
on-demand, paid, verifiable service that any human or any other agent can hire
through CAP.

**Tracks:** Research & Intelligence Agents (paid reasoning over novel problems)
and Data & Verification Agents (every delivery is deterministic and includes a
reproducible proof hash, so a buyer can verify the agent didn't change its
method between checking training pairs and predicting the test answer).

## Why this agent, not another LLM wrapper

Most agents on a commerce layer are thin wrappers around an LLM call —
hard to verify, non-deterministic, and easy to fake in a demo. This agent
instead sells a capability with an objective, checkable answer: given a
handful of input→output grid examples, infer the transformation rule and
apply it to a new input. The delivery is not prose — it's a JSON object
containing the predicted grid, the exact rule that was verified against
every training example, a confidence score, and a SHA-256 hash of the
reasoning payload, so a customer (or another agent acting on a customer's
behalf) can audit exactly what happened.

This also demonstrates real **A2A composability**: any orchestrator agent
that occasionally hits a visual-pattern sub-task it can't solve internally
can subcontract just that sub-task to this agent for a few cents, instead
of building grid-reasoning into every agent that might need it — the same
"hire a specialist instead of doing it yourself" logic that makes the rest
of the economy work.

## Architecture

```
                 ┌─────────────────────────┐
   Requester     │   CROO CAP (L3)          │      Provider
   (customer     │   Order Lifecycle:       │      (this repo)
   or another  ─►│   Negotiate→Lock→        │◄──   croo_arc_agent/provider.py
   agent)        │   Deliver→Clear          │      croo_arc_agent/solver.py
                 │   Escrow · Settlement ·  │
                 │   On-chain Reputation    │
                 └─────────────────────────┘
```

- **L1 (below CAP):** the agent's DID and AA wallet, created when you register
  the agent in the [CROO Dashboard](https://agent.croo.network).
- **L3 (CAP, what this repo integrates):** negotiation, escrow-backed payment,
  verifiable delivery, and settlement — all via `@croo-network/sdk`'s Python
  port, `croo-sdk`.
- **Execution (this repo, runtime-agnostic):** `croo_arc_agent/solver.py` is
  pure Python with zero CAP dependencies — it can be swapped for a stronger
  solver (e.g. a multi-strategy ARC-AGI-2 solver) without touching the
  networking code at all.

## Repository layout

```
croo-arc-agent/
├── croo_arc_agent/
│   ├── solver.py          # pure-Python puzzle solver (no network calls)
│   ├── provider.py         # CAP provider: listens, validates, solves, delivers
│   ├── requester_demo.py   # CAP requester used to record the demo video
│   ├── solve_offline.py    # CLI to test the solver with zero CAP credentials
│   └── config.py           # env var loading shared by provider/requester
├── examples/
│   └── sample_task.json    # known-answer puzzle used by tests + the demo
├── tests/
│   └── test_solver.py      # pytest unit tests, no network required
├── .env.example
├── requirements.txt
├── pyproject.toml
└── LICENSE                 # MIT
```

## Setup

### 1. Register two agents in the CROO Dashboard

You need **two** CAP agents to demo the full order lifecycle: one Provider
(this service) and one Requester (a test customer).

1. Go to [agent.croo.network](https://agent.croo.network) and sign in.
2. **My Agents → Register Agent** → name it (e.g. "ARC Reasoning Solver").
   This mints an AA wallet and an Agent DID, and shows you an **API Key once**
   — copy it immediately, this becomes `CROO_SDK_KEY` for the provider.
3. On the Configure page, fill in:
   | Field | Value |
   |---|---|
   | Description | "Solves ARC-AGI-style abstract grid-reasoning puzzles from a few input/output examples." |
   | Skill Tags | reasoning, verification, research (pick whatever subset your dashboard offers) |
   | Service Name | "ARC Abstract Reasoning Solver" |
   | Price | e.g. `0.25` USDC per call |
   | SLA | `0h 2m` (the solver itself runs in milliseconds) |
   | Deliverable | `Schema` |
   | Requirements | `Schema` |
4. Repeat steps 2–3 to register a **second** agent to act as the Requester
   (used only for testing / the demo video). You don't need to add a service
   to the Requester agent.
5. Deposit a small amount of **USDC on Base** to the Requester agent's **AA
   wallet address** (visible on its Configure page) — not the controller
   address. Gas is sponsored by CROO during the launch window; you only need
   USDC to cover the service price.
6. Copy the **Provider's Service ID** (shown on its Configure page after you
   save the service) — this becomes `CROO_TARGET_SERVICE_ID` for the requester.

### 2. Install

```bash
git clone <this-repo-url>
cd croo-arc-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
# edit .env: paste the Provider's CROO_SDK_KEY
```

The requester needs a *different* SDK key (its own agent's key) plus the
provider's service ID — keep those in a second file, e.g. `.env.requester`,
or export them directly in the shell you use to run the demo script.

### 4. Run the provider

```bash
export $(grep -v '^#' .env | xargs)   # or use python-dotenv / direnv
python -m croo_arc_agent.provider
```

You should see `ARC provider agent online — waiting for orders...` and the
agent's status in the Dashboard flips to **Online**.

### 5. Run the requester demo (in a second terminal)

```bash
export CROO_API_URL="https://api.croo.network"
export CROO_WS_URL="wss://api.croo.network/ws"
export CROO_SDK_KEY="croo_sk_...requester_key..."
export CROO_TARGET_SERVICE_ID="<provider service id>"
python -m croo_arc_agent.requester_demo
```

This negotiates a real order against the provider, pays it (a real on-chain
USDC transaction settled through the CAP escrow contract), waits for the
delivered prediction over the WebSocket, downloads it, and locally checks it
against the puzzle's known answer (`examples/sample_task.json`).

### 6. (Optional) Test the solver with zero CAP credentials

```bash
python -m croo_arc_agent.solve_offline examples/sample_task.json
pytest tests/ -v
```

## SDK methods used (`croo-sdk` / `AgentClient`)

| Method | Used in | Purpose |
|---|---|---|
| `connect_websocket()` | provider.py, requester_demo.py | Open the real-time event stream |
| `get_negotiation(id)` | provider.py | Fetch the task JSON a customer sent |
| `accept_negotiation(id)` | provider.py | Accept a valid negotiation → creates the on-chain order |
| `reject_negotiation(id, reason)` | provider.py | Reject malformed/invalid task requests before any money moves |
| `get_order(id)` | provider.py | Recovery path if the provider process restarts mid-order |
| `reject_order(id, reason)` | provider.py | Fail gracefully if the solver itself errors after payment |
| `deliver_order(id, req)` | provider.py | Submit the verified prediction as a `Schema` deliverable |
| `negotiate_order(req)` | requester_demo.py | Start a negotiation against the provider's service |
| `pay_order(id)` | requester_demo.py | Pay into CAP escrow once the order is created |
| `get_delivery(id)` | requester_demo.py | Download the provider's delivered prediction |

Event types consumed: `NEGOTIATION_CREATED`, `NEGOTIATION_REJECTED`,
`NEGOTIATION_EXPIRED`, `ORDER_CREATED`, `ORDER_PAID`, `ORDER_COMPLETED`,
`ORDER_REJECTED`, `ORDER_EXPIRED`.

## Integration notes

- **Task validation happens before acceptance, not after payment.** The
  provider parses and schema-checks the negotiation's `requirements` field
  and calls `reject_negotiation()` for anything malformed, so a customer
  never pays for a request the agent can't actually serve.
- **Deterministic, auditable delivery.** `solver.py` only ever reports a
  strategy as "used" if it exactly reproduces *every* training pair — there
  is no partial-credit guessing dressed up as confidence. The `reasoning_hash`
  in the delivery lets a customer re-derive the same hash from the same
  training pairs and strategy name, which is the verification story behind
  the Data & Verification track.
- **Crash-safe.** If the provider process restarts between accepting a
  negotiation and the order being paid, `_handle_order_paid` re-fetches the
  task from the order's negotiation instead of losing it.
- **Swappable solver.** `solve_task(task) -> SolveResult` is the entire
  contract `provider.py` depends on. Replace the body of `solver.py` with a
  stronger ARC-AGI-2 solver and nothing else in this repo needs to change.

## License

MIT — see [LICENSE](LICENSE).
