## Course coverage: Mastering Agentic AI → LaneRoom

How each topic from the Week 1-5 sessions and The Gen Academy repos shows up in LaneRoom, and where to point
during the demo. **✅ shown** = visible in the app or eval. **◐ partial** = present but light.
**○ not used** = deliberately out of scope, with the reason, so you can answer the question if a judge asks.

### Week 1 · Gen AI building blocks, harness, frameworks

| Topic | Status | Where in LaneRoom |
|---|---|---|
| Tokens, cost and context windows | ✅ | Every agent records LLM calls, tokens in/out and estimated cost. See the **Agent log** tab and the eval report's cost per memo. Prices are set in `.env` (`LR_PRICE_*`) |
| Model selection, open vs closed, OpenAI-compatible APIs | ✅ | One client for Nebius (Llama 3.3 70B), OpenAI or a local Ollama model: change only `FS_LLM_BASE_URL` / `FS_LLM_MODEL` |
| Non-determinism | ✅ | LLM agents run at low temperature (0 for the Verifier, 0.4 at most). Offline agents are fully deterministic, so tests and CI are reproducible |
| Prompt anatomy, prompt as procedure | ✅ | Role, task, constraints and output schema per agent in `src/laneroom/prompts.py` |
| Agent harness: loop, context, tools, guardrails, verification, error recovery | ✅ | LangGraph loop, tool access through MCP, step limits (`LR_MAX_VERIFY_RETRIES`), the Verifier checks every claim, and any failed LLM call falls back to the offline agent |
| Structured output | ✅ | Planner, both advocates, Rebuttal and Verifier return JSON in a fixed schema, which is parsed and validated (`llm.chat_json`) |
| Function calling / tools | ✅ | `search_filings`, `get_page`, `lane_scorecard`, `key_metrics`, `compute_change`, exposed as MCP tools |
| LangChain core primitives | ✅ | `ChatOpenAI`, messages, documents, Chroma and BM25 retrievers |
| n8n / no-code automation | ○ | Python-first project. The MCP server lets an n8n or other MCP client call the same tools |

### Week 2 · RAG and context engineering

| Topic | Status | Where in LaneRoom |
|---|---|---|
| Chunking, embeddings, vector store | ✅ | Semantic chunks of the J.B. Hunt, C.H. Robinson and Old Dominion FY2025 10-Ks plus the synthetic Armada profile, Chroma with all-MiniLM-L6-v2 (reused from our Week 2 FilingSight project via LaneRoom) |
| Hybrid search (BM25 + dense), RRF, reranking | ✅ | Researcher's `search_filings` tool |
| Metadata filtering | ✅ | Provider, Item, page and a synthetic flag on every chunk. Searches filter by provider (tickers and typos such as ODLF resolve) |
| Context engineering: what goes in, ordering, compression | ✅ | Each agent gets only its evidence pack (ids, company, page, item, text), capped per passage. Retrieved text is sanitised before it reaches a prompt |
| Memory: working, episodic, semantic | ✅ | Working = graph state. Episodic = approved awards. Semantic = shipper mandate (cost-first / balanced / service-first), preferred KPIs and incumbent (long-term store) |
| Agentic RAG: the agent decides to search again | ✅ | Researcher re-searches any sub-question whose results are weak, using a reformulated query (LLM rewrite or keyword rewrite). The Agent log shows how many re-searches ran |
| ReAct loop: think, act, observe | ✅ | Verifier → Revise → Verifier: rejected claims go back to their author with the reason (max 2 loops) |
| RAG evals: retrieval first, then answer | ✅ | hit@5 and MRR on 22 labelled carrier questions, citation faithfulness, and the planted false claim |
| Graph RAG / Cypher | ○ | The questions are about one provider's filing and one lane at a time, not multi-hop relationships, so a knowledge graph would add cost without better answers (the "when graph RAG is worth it" test from the session) |

### Week 3 · Multi-agent systems, LangGraph, MCP, A2A

| Topic | Status | Where in LaneRoom |
|---|---|---|
| LangGraph state machine, conditional edges | ✅ | `src/laneroom/graph.py`: 14 nodes, a retry loop, and routing after review |
| Multi-agent patterns: planner, parallel fan-out, debate, judge | ✅ | Planner → Researcher and Quant in parallel → Cost and Resilience advocates in parallel → Rebuttal → Verifier → Judge (allocation) → Writer |
| Not every agent needs an LLM (Project 3B hint) | ✅ | Guardrail, Quant and the allocation Judge are rules and math. Only reasoning steps use the LLM |
| Human in the loop (`interrupt`) | ✅ | The graph pauses before saving: approve, ask for changes, or ask a follow-up |
| MCP: host, client, server, tools | ✅ | `src/laneroom/mcp_server.py` (FastMCP, stdio). Toggle **Researcher uses the MCP server** in the sidebar |
| Production cost and latency | ✅ | Parallel nodes, capped candidates, per-node timing, tokens and cost in the trace |
| A2A (agent-to-agent protocol) | ○ | All agents run in one process and share one graph state, so no cross-service agent contract is needed. MCP covers the tool boundary |
| Deep Agents | ○ | The task is a fixed committee procedure, so an explicit graph is easier to test than an open planning agent |

### Week 4 · Evals, observability, monitoring

| Topic | Status | Where in LaneRoom |
|---|---|---|
| Golden dataset and offline evals | ✅ | `eval/run_eval.py`: labelled retrieval questions, Quant figures checked against the filing, allocation validity, mandate sensitivity, guardrail cases, committee runs |
| LLM as judge | ✅ | In LLM mode the Verifier adds an LLM judge on top of the rule checks |
| Cost and latency as eval dimensions | ✅ | Median and p95 seconds, tokens and estimated cost per memo in the eval report |
| Tracing and observability | ✅ | Every run's agent trace is written to `data/traces/runs.jsonl`. Set `LANGSMITH_TRACING=true` to send full traces to LangSmith (the sidebar shows when it is on) |
| Turning logs into eval cases, feedback loop | ✅ | Every human review decision is logged to `data/eval/feedback.jsonl`. `python eval/run_eval.py --feedback` replays those requests as regression cases |
| Regression testing and CI | ✅ | 38 pytest tests and the eval run offline with no API key, so they are reproducible and CI ready |
| Baseline comparison | ✅ | Plain RAG (Week 2 FilingSight on the same corpus) vs the LaneRoom committee on the same prompts |
| Alerts and dashboards | ◐ | Thresholds sit in the eval report targets. No live alerting, because the demo is a local app |

### Week 5 · Fine-tuning and local models

| Topic | Status | Where in LaneRoom |
|---|---|---|
| Running models locally with Ollama | ✅ | Point the OpenAI-compatible client at Ollama (see `.env.example`). The sidebar engine label shows "local, Ollama". Filings, the shipper's scorecard and prompts never leave the machine, and the cost estimate drops to $0 |
| Privacy, cost, compliance of local inference | ✅ | Same as above, plus offline agents that need no model at all |
| Decision framework: prompt vs RAG vs fine-tune | ◐ | We chose RAG + prompting: the facts live in the filings and must be cited by page, which fine-tuning cannot guarantee |
| Fine-tuning (SFT, LoRA, DPO, RFT/RLVR), distillation, synthetic data | ○ | Not needed for this task. A natural next step: distil the LLM Verifier into a small local model, using the logged Verifier decisions as training data |

### Course projects that LaneRoom builds on

| Repo | What we reused |
|---|---|
| DealRoom (our sibling project) | Whole architecture: graph, Verifier loop, human review, memory, MCP server, eval harness and UI theme |
| 3B Multi-Agent Deal Review Pipeline | Parallel expert panel, rule-based agents where no LLM is needed, synthesis, human review before the report |
| 2B Financial Document Intelligence Pipeline / Week 2 | Our FilingSight hybrid RAG over 10-K filings is LaneRoom's knowledge base |
| Week 3 Session 1 (LangGraph) | ReAct and multi-agent workflow patterns |
| Week 4 Sessions 1-2 (evals) | Golden datasets, RAG evals, regression mindset |
| Week 5 Session 2 (Ollama) | Local model option through the OpenAI-compatible endpoint |
