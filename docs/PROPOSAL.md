# Team 24 Demo Day proposal: LaneRoom

**Team 24 · The Gen Academy, Mastering Agentic AI · November 2026**
Repo: https://github.com/balum211/LaneRoom · Sibling project: https://github.com/balum211/DealRoom

LaneRoom is a team of AI agents that runs a shipper's freight tender committee in seconds. It reads carriers' SEC
filings and the shipper's own lane scorecard, has a **Cost** advocate and a **Resilience** advocate argue how to
split a lane's loads, checks every claim against the page or scorecard row it cites, and hands a human a cited memo
with a recommended **allocation % per carrier** to approve.

## Problem and users

Shippers re-bid their lanes every year and re-allocate them every peak season. A procurement analyst has to weigh
tender acceptance, on-time service, rate per mile and claims from the TMS against each carrier's capacity and
financial health from its 10-K, and then defend the split to operations and finance. Today that is a spreadsheet,
a few 100-page filings and a gut call. Plain chatbots fall short in three ways:

- **No decision.** They summarise carriers but do not produce an allocation that respects procurement rules.
- **Unverifiable numbers.** A rate or an operating ratio without a source cannot go into an award memo.
- **One lens.** Cheapest-rate thinking ignores peak-season capacity risk, and vice versa.

| User | Job to be done | What LaneRoom gives them |
|---|---|---|
| Transportation procurement analyst | Split a lane's weekly loads across carriers | A cited allocation with loads per week and the rules applied |
| Logistics / operations manager | Protect service in peak season | The Resilience case, Q4 acceptance and backup capacity |
| Finance or category lead | Understand the cost trade-off | The Cost case, rate per mile and carrier financial health |

## Solution: why it is agentic, not just RAG

1. **Planning.** A Planner detects the lane, the providers and the load count, and splits the request into capacity,
   cost, financial health, service and risk sub-questions per provider.
2. **Tool use.** Agents call a hybrid filing search, a table-reading metrics tool, a lane scorecard tool and a change
   calculator. The same tools are served by an **MCP server** that any MCP client can use.
3. **Multi-agent debate.** Cost and Resilience advocates get the same evidence but opposite briefs, run in parallel,
   then one rebuttal round. A Judge turns it into an allocation.
4. **Self-correction.** A Verifier rejects claims whose quote is not on the cited page or scorecard row, whose
   numbers are not in the source, or whose provider does not match, and sends them back (max 2 loops).
5. **Human in the loop.** The graph pauses with `interrupt()` before anything is awarded or saved.
6. **Memory.** Thread memory (LangGraph checkpointer) and long-term shipper memory (cost-first vs service-first
   mandate, preferred KPIs, incumbent, past awards) that changes how the Judge allocates.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the graph, the agent table and the allocation rules.

| Layer | Choice |
|---|---|
| Orchestration | LangGraph: parallel fan-out (Researcher + Quant, Cost + Resilience), conditional retry loop, interrupt for human review, checkpointer |
| LLM | Any OpenAI-compatible model via LangChain (Nebius Llama-3.3-70B by default); deterministic offline agents when no key is set |
| Retrieval | Reused from our Week 2 project FilingSight (via DealRoom): semantic chunks, Chroma (MiniLM ONNX) + BM25, Reciprocal Rank Fusion, local reranker, provider filters |
| Data | J.B. Hunt, C.H. Robinson and Old Dominion FY2025 Form 10-K (SEC EDGAR) + **synthetic** profiles for four private providers (Armada, Edge Logistics, First Star, BlueGrace Logistics), 1,033 chunks with provider, page and Item metadata; a **synthetic** 80-row lane scorecard |
| Tools | MCP server (`laneroom-carriers`): `search_filings`, `get_page`, `list_companies`, `lane_scorecard`, `key_metrics`, `compute_change` |
| UI | Streamlit 3D glass theme with a freight-orange accent: animated US route map with moving trucks, per-lane route card, pydeck arc map, carrier badges and roster, live agent timeline, allocation bar, debate view with verification badges, scorecard and financial cards, memo, evidence viewer, approve / revise / follow-up |
| Quality | pytest suite (42 tests), evaluation script, GitHub Actions CI |

## Guardrails

- **Input:** prompt-injection patterns, empty or oversized requests, off-topic requests and carriers outside the
  knowledge base are refused; stock buy/sell questions get a freight allocation, not investment advice.
- **Evidence:** instruction-like lines in retrieved text are stripped before any agent sees them.
- **Grounding:** a claim that fails verification never reaches the memo.
- **Allocation:** ≤ 60% per carrier, ≥ 10% backup share, acceptance floor 80%, synthetic-data cap 25%.
- **Output:** stock buy/sell language is removed and a disclaimer is always added; synthetic data is labelled everywhere.
- **Cost and loops:** at most 2 verification retries and 1 rebuttal round; tokens and cost tracked per agent.

## Evaluation

`python eval/run_eval.py` measures citation faithfulness, whether an injected false claim is caught, allocation
validity, mandate sensitivity, Quant accuracy against the printed filing values (29/29), retrieval hit@5 on 25
labelled carrier questions, debate balance, guardrail decisions, latency and cost, and a side-by-side with plain RAG.
Latest results: [eval/results/summary.md](../eval/results/summary.md) and the app's Evaluation tab.

## Demo script

See [DEMO_SCRIPT.md](DEMO_SCRIPT.md) (about 3 minutes).

## Team and plan

**Team 24:** Bala Mallampati, Ravindranath Konduru (Ravi), Deepthi Avula and Neha Madhao Pande.

One owner per workstream; everyone reviews and rehearses the demo.

| Team member | Owns |
|---|---|
| **Bala Mallampati** | LangGraph orchestration, the advocate and Judge agents, allocation rules, human review and memory |
| **Ravindranath Konduru** | EDGAR ingestion, chunking, hybrid retrieval, the lane scorecard and the MCP carrier server |
| **Deepthi Avula** | Streamlit UI, allocation and debate views, README and the demo video |
| **Neha Madhao Pande** | Evaluation set, LLM judge, guardrails, synthetic-data labelling and the Demo Day slides |

1. **Nov 6 (done):** full committee graph over the FY2025 10-Ks, synthetic private-provider profiles and scorecard, MCP server,
   human approval, memory, Streamlit UI and eval suite with cost and latency tracking.
2. **Nov 7 to 8:** run the eval with LLM agents and an API key to measure real tokens and cost per memo, tune prompts,
   rehearse.
3. **Nov 9 to 10 (if shortlisted):** load a real shipper TMS export in place of the synthetic scorecard, add more
   carriers (Knight-Swift, Werner, Saia), live Demo Day rehearsal.

| Risk | Fallback |
|---|---|
| LLM slow or rate limited on stage | Offline agents run the same graph with no key; a recorded run as backup |
| Judges ask whether the tender data is real | Every screen, the memo and the README label the scorecard and the private-provider profiles as synthetic; the 10-K figures are real and page-cited |
| Agents loop or overspend | Hard caps on Verifier retries and debate rounds; tokens and cost tracked per agent |
| Filing tables parse badly | Quant reads named table rows and is tested against the printed figures (29 of 29 match) |

**Future work:** live EDGAR fetch for any carrier ticker, a TMS/CSV upload for the shipper's real scorecard,
spot-vs-contract rate benchmarks, multi-lane network optimisation, and pushing approved awards to the TMS.
