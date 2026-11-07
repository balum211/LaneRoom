# Demo video script (about 3 minutes)

**Recorded demo:** https://www.loom.com/share/230491153e4546378afab6933ceb111a

**Setup before recording**
1. `run.bat` (or `streamlit run app.py`), wait for the page to load.
2. Run the first scenario once so the index is warm, then refresh.
3. Sidebar: name `demo`, mandate **balanced**, turn on **Stress test: plant a false claim**.
4. Optional: add an API key to `.env` so the Agent log shows real token and cost numbers. For a local model, use the
   Ollama lines in `.env.example`. For LangSmith traces, set `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY`.
5. Record the browser window with Windows `Win + Alt + R` (Xbox Game Bar) or OBS / Loom.

| Time | On screen | Say |
|---|---|---|
| 0:00 to 0:15 | App title | "We're Team 24. This is LaneRoom, an AI tender committee that tells a shipper how to split a freight lane between carriers, with every number cited." |
| 0:15 to 0:30 | Click **Dallas→Atlanta 500 loads**, then **Convene committee** | "One request in: 500 weekly dry-van loads, Dallas to Atlanta. A guardrail checks it, and a Planner picks the lane, the carriers and the load count, then splits the work into capacity, cost, financial health, service and risk." |
| 0:30 to 0:55 | Pipeline: Researcher and Quant finish | "The Researcher searches J.B. Hunt's, C.H. Robinson's and Old Dominion's FY2025 10-Ks with hybrid search, over an MCP server if we want, and re-searches weak results. Armada, Edge Logistics, First Star and BlueGrace Logistics are private, so their documents are synthetic, illustrative profiles, and the lane scorecard is synthetic shipper data. The Quant reads revenue, operating income and cash flow straight from the filings' tables." |
| 0:55 to 1:20 | **Debate** tab: Cost and Resilience columns, rebuttal | "Two advocates argue: Cost wants the cheapest rate per mile, Resilience wants acceptance and peak-season capacity. Then they rebut each other." |
| 1:20 to 1:40 | The red "rejected" claim C0 and its replacement | "We planted a false claim: J.B. Hunt accepted 100 percent of tenders at a dollar fifteen a mile. The Verifier checked the scorecard row, rejected it, and the advocate replaced it with a supported one." |
| 1:40 to 2:00 | Verdict card, the **Route map** card (one coloured route per carrier on a real map, trucks moving) and the Google Maps driving route under it, then **Network map**, **Memo**, **Evidence** | "The Judge turns verified evidence into an award: 45 percent J.B. Hunt, then C.H. Robinson, Armada, BlueGrace and Edge Logistics. The route map draws each carrier's share of the lane. No carrier gets more than 60 percent, everyone qualified keeps backup volume, and the private carriers are capped because their profiles are synthetic. The memo footnotes every claim to a 10-K page or a scorecard row." |
| 2:00 to 2:05 | Value strip under the verdict, then the **Business value** tab | "And what is it worth? For this lane about 300 thousand dollars a year net: weeks of 10-K review become a minute, backhaul offers are answered while they are still open, and more carriers can bid. The award mix even shows the premium we pay for service. Every assumption is editable, and the numbers are illustrative because the scorecard is synthetic." |
| 2:05 to 2:20 | Switch mandate to **service-first**, pick **Peak surge**, convene again | "Change the shipper's mandate in memory to service-first, and the peak-season award shifts toward Old Dominion's on-time service." |
| 2:20 to 2:35 | **Agent log** tab, then **Approve allocation** | "Every agent is traced with time, LLM calls, tokens and cost. A human approves before anything is saved, and approvals go into long-term memory." |
| 2:35 to 2:50 | **Evaluation** tab | "On our eval: 100 percent of final claims verified, the planted claim caught every time, 29 of 29 filing and profile figures exact, and every allocation follows the tender rules." |
| 2:50 to 3:00 | **Course map** tab | "And this maps Weeks 1 to 5 of the course to LaneRoom. Code is on GitHub. Thanks!" |

Tips
- The whole committee takes about 15 to 30 seconds on a laptop.
- Say clearly that the scorecard and the four private-carrier profiles are synthetic; the 10-K figures are real. The carrier badges are our own designs, not company logos.
- The Agent log shows 0 tokens and $0 with offline agents. Say "offline agents need no API key, so this run is free",
  or record with an API key to show real numbers.
