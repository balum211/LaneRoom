# Demo Day submission (Team 24): LaneRoom

Form: https://forms.gle/rYC7PCaDg1xj9ZVu8 · Deadline: **Thursday Nov 6, 2026, 11:59 pm PT**

| Form field | What to enter |
|---|---|
| Team number | 24 |
| Contributing members | Bala Mallampati, Ravindranath Konduru (Ravi), Deepthi Avula and Neha Madhao Pande |
| Completed breakout activity document | `Team24_LaneRoom_Proposal.pdf` (or the .docx) uploaded to Google Drive with "Anyone with the link can view", or a link to [docs/PROPOSAL.md](PROPOSAL.md) |
| GitHub link | https://github.com/balum211/LaneRoom |
| Live app | https://laneroom-team24.streamlit.app |
| Video demo (Drive link) | Your Google Drive link, sharing set to "Anyone with the link can view" (script: [DEMO_SCRIPT.md](DEMO_SCRIPT.md)) |

**One-line description (if the form asks):** LaneRoom is a multi-agent freight tender committee: a Planner,
Researcher, Quant, Cost and Resilience advocates, a Verifier, a Judge and a Writer read carriers' SEC 10-Ks and a
lane scorecard, debate cost against service, fact-check every claim and recommend a tender allocation % per carrier
that a human approves, built with LangGraph, an MCP server, Streamlit and an evaluation suite.

**Data note to keep in every description:** J.B. Hunt, C.H. Robinson and Old Dominion figures come from their real
FY2025 10-Ks. Armada is privately held, so its profile is synthetic, and the lane scorecard (tender acceptance,
on-time %, rate per mile, claims %) is synthetic demo data for all carriers.

## Headline results (offline agents, no API key)

| Metric | Result |
|---|---|
| Citation faithfulness | 100% |
| Planted false claim caught by the Verifier | 100% |
| Valid allocations (sum to 100%, ≤ 60% per carrier, synthetic cap 25%) | 100% |
| 10-K figures read correctly | 17/17 |
| Retrieval hit@5 / MRR (22 labelled questions) | 100% / 0.93 |
| Guardrail decisions | 8/8 |
| Tests | 38 passing |

## Live app (Streamlit Community Cloud)

- URL: https://laneroom-team24.streamlit.app · repo `balum211/LaneRoom`, branch `main`, main file `app.py`, Python 3.12.
- Runs with **offline agents** by default, so it costs nothing and needs no key. To show the LLM agents, add
  `NEBIUS_API_KEY = "..."` under the app's **Settings → Secrets** (top-level secrets become environment variables).
- The first visit after the app sleeps takes 1 to 2 minutes (install, 80 MB embedding model download, index load).
  Open it once before the demo.
- Approved awards are saved to the app's local disk, which resets when the app restarts. That is fine for a demo.

## Checklist
- [x] Repo is public: https://github.com/balum211/LaneRoom
- [x] README with screenshots, architecture, proposal, demo script, course map
- [ ] CI badge green on the latest commit
- [ ] Live app opened once and the Dallas→Atlanta scenario run end to end
- [ ] Video recorded (2 to 3 minutes) and uploaded to Drive with link sharing on
- [ ] Proposal document uploaded to Drive with link access
- [x] Team members confirmed: Bala Mallampati, Ravindranath Konduru (Ravi), Deepthi Avula and Neha Madhao Pande
- [ ] Form submitted before 11:59 pm PT (submit without the video if it is not ready; it can be shared later)
