# BACOWR Experimental — Teknikguide & Snabbreferens

> Referens för LangChain, LangGraph, CrewAI, Swarms och relaterade verktyg.  
> Använd vid val av ramverk för skillifierad pipeline eller multiagent-approach.

---

## 1. Översikt per approach

| Approach | Primära ramverk | Sekundära | När att välja |
|---------|-----------------|-----------|---------------|
| **Skillifierad pipeline** | Lättviktig (JSON + scripts) | LangChain, LlamaIndex | Steg-för-steg med tydliga kontrakt, resume |
| **Multiagent (2–3 huvudagenter)** | LangGraph, CrewAI | Swarms | Specialiserade agenter, subagent-delegation |

---

## 2. LangChain & LangGraph

### LangChain (LCEL, Chains)

- **Användning:** Sekvensiella steg, output parsers, retries, fallbacks
- **Install:** `pip install langchain langchain-openai` (eller -anthropic)
- **BACOWR-relevans:** Bra för skill-kedjor där varje steg har strukturerad output
- **Dokumentation:** https://python.langchain.com/
- **Observability:** LangSmith (spårning, debugging)

### LangGraph (Stateful graphs)

- **Användning:** Multiagent workflows, branching, conditional routing, state machines
- **Install:** `pip install langgraph`
- **BACOWT-relevans:** Research → Content → QA med conditional "remediate" loop
- **Kärnkoncept:** StateGraph, nodes, edges, conditional_edges, checkpointer
- **Dokumentation:** https://langchain-ai.github.io/langgraph/
- **Fördel:** Explicit kontroll, ingen "magisk" delegation

### Snabbkod (LangGraph)

```python
from langgraph.graph import StateGraph, END

# Definiera state
class BacowrState(TypedDict):
    job: dict
    preflight: dict
    blueprint: dict
    article: str
    qa_passed: bool

# Bygg graph
graph = StateGraph(BacowrState)
graph.add_node("research", research_node)
graph.add_node("content", content_node)
graph.add_node("qa", qa_node)
graph.add_node("remediate", remediate_node)
graph.add_edge("research", "content")
graph.add_edge("content", "qa")
graph.add_conditional_edges("qa", lambda s: "remediate" if not s["qa_passed"] else "end", {"remediate": "remediate", "end": END})
graph.add_edge("remediate", "content")
```

---

## 3. CrewAI

- **Användning:** Rollbaserade agenter, task delegation, hierarchical teams
- **Install:** `pip install crewai crewai-tools`
- **BACOWR-relevans:** Research Crew (Preflight, Metadata, SERP, Trustlink) + Content Crew (Blueprint, Writer, QA)
- **Kärnkoncept:** Agent (roll, goal, backstory), Task (description, expected_output), Crew (agents, tasks), Process (sequential, hierarchical)
- **Dokumentation:** https://docs.crewai.com/
- **Hierarchical Process:** Manager-LLM koordinerar, delegating till workers

### Snabbkod (CrewAI)

```python
from crewai import Agent, Task, Crew, Process

researcher = Agent(role="Researcher", goal="Gather preflight and SERP data")
writer = Agent(role="Writer", goal="Write article from blueprint")

research_task = Task(description="Preflight + metadata + SERP", agent=researcher)
write_task = Task(description="Write 750-900 word article", agent=writer, context=[research_task])

crew = Crew(agents=[researcher, writer], tasks=[research_task, write_task], process=Process.hierarchical)
result = crew.kickoff(inputs={"job": job_spec})
```

---

## 4. Swarms

- **Användning:** Coordinator + sub-agents, dynamisk task distribution, Python-native
- **Install:** `pip install swarms`
- **BACOWR-relevans:** Coordinator skapar Preflight Worker, SERP Worker etc. on-the-fly
- **Kärnkoncept:** Agent, create_sub_agent, assign_task, selected_tools
- **Dokumentation:** https://docs.swarms.ai/
- **Fördel:** Låg latency, minimal overhead

### Subagent-delegation (Swarms)

- `max_loops="auto"` för att tillåta sub-agents
- Coordinator använder `create_sub_agent` och `assign_task` för att distribuera arbete
- Bra för parallell SERP-probes (olika workers kan köra olika queries samtidigt)

---

## 5. LlamaIndex

- **Användning:** RAG, document indexing, retrieval över knowledge base
- **Install:** `pip install llama-index`
- **BACOWR-relevans:** Om du vill bygga retrieval över historiska preflights/blueprints/artiklar
- **När:** Senare fas — inte nödvändigt för första iteration

---

## 6. Pydantic AI (alternativ)

- **Användning:** Typ-safe agents, strukturerad I/O
- **Install:** `pip install pydantic-ai`
- **Relevans:** Bra om du vill ha strikt typning i agent inputs/outputs
- **Dokumentation:** https://ai.pydantic.dev/

---

## 7. Beslutsträd: Vilket ramverk?

```
Behöver du multiagent med subagenter?
├── JA → Vill du ha maximal kontroll (state machine, gates)?
│   ├── JA → LangGraph
│   └── NEJ → Föredrar du rollbaserad "crew"-modell?
│       ├── JA → CrewAI
│       └── NEJ → Vill du ha snabb, experimentell parallisering? → Swarms
└── NEJ → Behöver du bara kedja steg med kontrakt?
    ├── Enkelt, utan extra deps → Lättviktig (JSON + scripts)
    ├── Retries, observability → LangChain
    └── RAG över historik → LlamaIndex (senare)
```

---

## 8. Dependencies (requirements.txt-snippet)

```txt
# Kärn-BACOWR (redan i core/)
aiohttp
beautifulsoup4
sentence-transformers  # valfritt, pipeline degraderar utan

# Skillifierad pipeline (valfritt)
jsonschema
pydantic

# LangChain/LangGraph
langchain
langchain-openai
langgraph

# CrewAI
crewai
crewai-tools

# Swarms
swarms
```

---

## 9. Viktiga länkar

| Ramverk | Docs | GitHub |
|---------|------|--------|
| LangChain | https://python.langchain.com/ | langchain-ai/langchain |
| LangGraph | https://langchain-ai.github.io/langgraph/ | langchain-ai/langgraph |
| CrewAI | https://docs.crewai.com/ | joaomdmoura/crewAI |
| Swarms | https://docs.swarms.ai/ | kyegomez/swarms |
| LlamaIndex | https://docs.llamaindex.ai/ | run-llama/llama_index |

---

*Skapad 2026-02-20. Uppdatera vid behov.*
