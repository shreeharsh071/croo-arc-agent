# Submission Checklist — map to the hackathon's 5 mandatory requirements

Every BUIDL must satisfy all five. Status reflects what's in this repo today
vs. what you still need to do on the CROO Dashboard / DoraHacks site.

| # | Requirement | What's needed | Status |
|---|---|---|---|
| 1 | **Listed on CROO Agent Store** | Register the provider agent + service in the Dashboard (agent.croo.network) — see README "Setup, step 1" | ⬜ You do this manually (cannot be scripted — it's identity/KYC-adjacent) |
| 2 | **Integrated with CAP, callable, settles on-chain** | `provider.py` integrates the full negotiate→accept→deliver lifecycle via `croo-sdk`; `requester_demo.py` proves a real on-chain payment | ✅ Code complete and tested in this repo |
| 3 | **Open source, permissive license** | `LICENSE` (MIT) included at repo root | ✅ Done |
| 4 | **Demo + README** (≤5 min video, setup, SDK methods, integration notes) | `README.md` has setup/SDK-methods/integration notes; you still need to record the video | ✅ README done · ⬜ Record video |
| 5 | **BUIDL filed on DoraHacks** | `DORAHACKS_WRITEUP.md` is ready to paste into the BUIDL form | ✅ Draft ready · ⬜ Submit on dorahacks.io |

## Before you record the demo video
1. Run `python -m croo_arc_agent.provider` in one terminal — leave it running.
2. Run `python -m croo_arc_agent.requester_demo` in a second terminal,
   screen-recording both.
3. Narrate, in this order, on camera:
   - "Here's the provider agent online and listening." (show the log line)
   - "I'm hiring it as a second agent — negotiating, then paying into CAP
     escrow." (show the tx hash printing)
   - "Here's the delivered prediction, with the verified strategy and a
     reasoning hash." (show the JSON)
   - "And here it is checked against the known correct answer." (show the
     CORRECT verdict)
   - Optional, to show robustness: send one malformed request and show the
     provider rejecting it before any payment — proves the agent doesn't
     just rubber-stamp every order.
4. Keep it under 5 minutes. A focused 2–3 minute video that clearly shows
   the on-chain payment and a correct, verified delivery beats a long one.

## Before you submit the BUIDL
- [ ] Repo is public on GitHub with the MIT `LICENSE` at the root
- [ ] README setup steps actually work from a clean clone (test this!)
- [ ] Provider agent shows **Online** in the Dashboard
- [ ] Service appears in the CROO Agent Store, discoverable by humans/agents
- [ ] Demo video uploaded and linked, ≤5 minutes
- [ ] `DORAHACKS_WRITEUP.md` placeholders filled in and pasted into the form
- [ ] Correct track(s) selected on the form (max 2): Research & Intelligence
      + Data & Verification
- [ ] All fields on the DoraHacks BUIDL form completed, not just the writeup
      text (form usually also wants links, team info, and track selection
      as separate fields — fill those in too, not only the long-form text)
