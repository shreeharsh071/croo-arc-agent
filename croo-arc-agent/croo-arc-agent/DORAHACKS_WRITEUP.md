# DoraHacks BUIDL Writeup — ARC Reasoning Agent

Copy each section into the matching field on the DoraHacks BUIDL submission
form for the CROO Agent Hackathon. Replace every `<...>` placeholder before
submitting.

---

## Project Name
ARC Reasoning Agent

## Tagline (one line)
A paid CAP agent that solves abstract grid-reasoning puzzles and proves its work with a verifiable, deterministic delivery hash.

## Tracks
- Research & Intelligence Agents
- Data & Verification Agents

## Problem
AI agents can already execute narrow capabilities extremely well, but there
is no standard way for one agent to discover, hire, pay, and trust another
agent for a single sub-task. Without CAP, an orchestrator agent that needs a
specialized capability — like inferring a transformation rule from a handful
of examples — has to either build that capability in-house or call an
unverifiable, unpriced API with no settlement guarantees and no proof the
delivered answer is what it claims to be.

## Solution
We built a CAP **Provider** agent that sells exactly one capability:
inferring the transformation rule behind an ARC-AGI-style grid puzzle from
its training examples, and applying that rule to a new input. Every order
goes through CAP's full Negotiate → Lock → Deliver → Clear lifecycle:

1. A customer (human via the Agent Store, or another agent) negotiates an
   order, sending the puzzle as structured JSON in `requirements`.
2. The provider validates the schema and rejects malformed requests before
   any escrow is created — customers never pay for a request the agent
   can't serve.
3. Once the customer pays into CAP's on-chain escrow, the provider runs its
   solver, which only reports a strategy as "used" if it reproduces every
   single training example exactly — no partial-credit guessing.
4. The delivery is a JSON object: the predicted grid, the exact rule that
   was verified, a confidence score, and a SHA-256 hash of the reasoning
   payload, so the buyer can independently re-derive the same hash from the
   same training pairs and confirm the agent didn't change its method
   between checking the training examples and predicting the answer.
5. CAP verifies the delivery and auto-settles payment to the agent's wallet,
   writing a reputation (PTS) update to its DID.

## Why this is a strong fit for CAP / A2A composability
This is a deliberately narrow, well-defined, cheaply-priced capability —
exactly the shape of service that's worth subcontracting rather than
rebuilding. Any orchestrator agent juggling many task types can keep its own
logic simple and hire this agent for the specific sub-task of "infer a grid
transformation rule," paying only a few cents per call, instead of
maintaining its own grid-reasoning code. That's the core CAP thesis: agents
specializing and trading services with each other on-chain.

## Tech stack
- Python 3.10+, `croo-sdk` (the official Python port of `@croo-network/sdk`)
- CAP order lifecycle: negotiation, escrow payment, schema delivery, on-chain
  settlement, WebSocket event streaming
- Pure-Python multi-strategy solver (geometric transforms, per-cell color
  remapping, tiling/scaling) — verification-first design, deterministic, no
  external LLM call in the hot path (so behavior is fully reproducible)

## What's verifiable in the demo
- A real on-chain USDC payment into CAP escrow (tx hash printed in the demo
  video and visible on Base)
- A delivered prediction that is checked, on camera, against the puzzle's
  known correct answer
- A second run showing the provider correctly **rejecting** a malformed
  request before any payment happens

## Links
- GitHub (MIT licensed): `<your-repo-url>`
- Demo video (≤5 min): `<your-video-url>`
- Live on CROO Agent Store: `<your-agent-store-listing-url>`
- Provider Service ID: `<service-id-from-dashboard>`

## Team
`<your name / handle>` — `<role, e.g. "solo builder">`
