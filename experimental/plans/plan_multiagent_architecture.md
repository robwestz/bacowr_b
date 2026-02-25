# Plan B — Multiagent-arkitektur (Utförlig)

> **Mål**: Testa orchestrerad multiagent-approach med 2–3 huvudagenter och upp till 5 subagenter per huvudagent.  
> **Status**: Redo för implementation vid återkomst.  
> **Baserat på**: BACOWR v6.2/v6.3 (2026-02-19)

---

## 1. Sammanfattning

| Aspekt | Beskrivning |
|--------|-------------|
| **Varför** | Specialiserade agenter per domän (research vs writing vs QA), möjlighet till parallellisering, tydlig ansvarsfördelning |
| **Topologi** | 2–3 huvudagenter (supervisors), vardera med 2–5 subagenter (workers) |
| **Rekommenderad teknik** | **LangGraph** för kontroll/determinism, **CrewAI** för rollmodell. Swarms för experimentell snabb parallisering |

---

## 2. Agent-topologi

### Alternativ 1: 2 huvudagenter (rekommenderad start)

```
                    ┌─────────────────────────────────┐
                    │      ORCHESTRATOR / COORDINATOR   │
                    │   (batch state, job routing)      │
                    └──────────────┬───────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
    ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
    │ RESEARCH AGENT   │  │ CONTENT AGENT    │  │ (valfritt: QA    │
    │ (Supervisor)     │  │ (Supervisor)     │  │  Supervisor)     │
    └────────┬────────┘  └────────┬────────┘  └─────────────────┘
             │                    │
    ┌────────┴────────┐  ┌────────┴────────┐
    │ Subagenter:     │  │ Subagenter:       │
    │ · Preflight     │  │ · Blueprint       │
    │ · Metadata      │  │ · Draft Writer    │
    │ · SERP Probe    │  │ · QA Checker      │
    │ · Trustlink     │  │ · Remediation     │
    │ · Evidence Ver. │  │ · Final Gate       │
    └─────────────────┘  └───────────────────┘
```

**Research Agent** ansvarar för:
- Preflight (batch)
- Metadata-patch (via web_search/web_fetch)
- SERP probes (5 sökningar)
- Trustlink discovery
- Evidence verification (att trustlinks är giltiga djuplänkar)

**Content Agent** ansvarar för:
- Blueprint-generering från enriched preflight
- Artikelskrivning (draft)
- QA-validering (via article_validator.py)
- Remediation (fixa specifika QA-fel)
- Final gate (11/11 PASS innan nästa jobb)

### Alternativ 2: 3 huvudagenter (renare separation, högre overhead)

```
    ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
    │ DATA/RESEARCH   │  │ WRITING         │  │ QA/RELEASE      │
    │ SUPERVISOR      │  │ SUPERVISOR      │  │ SUPERVISOR      │
    └────────┬────────┘  └────────┬────────┘  └────────┬────────┘
             │                    │                    │
    Preflight│                    │Blueprint           │QA Checker
    Metadata │                    │Draft Writer        │Remediation
    SERP     │                    │Entity Weaver       │Final Gate
    Trustlink│                    │                    │
```

**Fördelar:** Tydlig separation. Research → Writing → QA är naturliga faser.  
**Nackdelar:** Mer orchestration, fler handoffs, potentiellt högre tokenkostnad.

---

## 3. Teknikval: LangGraph vs CrewAI vs Swarms

### Jämförelse (2024–2025)

| Aspekt | LangGraph | CrewAI | Swarms |
|--------|-----------|--------|--------|
| **Paradigm** | Stateful graph, nodes + edges | Role-based teams, task delegation | Coordinator + sub-agents, Python-native |
| **Kontroll** | Explicit control flow, branching | Manager/LLM styr delegation | Coordinator med create_sub_agent, assign_task |
| **Kodning** | Python, StateGraph | Python, Agent + Task + Crew | Python, Agent + Swarm |
| **Observability** | LangSmith (bra integration) | CrewAI Dashboard | Mindre etablerad |
| **Enterprise** | LangChain-ekosystem (90M+ downloads) | 60% Fortune 500, 450M workflows/månad | Nyare, efficiency-fokuserad |
| **Token/latency** | Lägst latency i benchmarks | Låg token usage | Låg token, snabb execution |
| **Subagent-stöd** | Custom nodes kan spawna agenter | Hierarchical Process (manager_llm) | Inbyggt: create_sub_agent, assign_task |

### Rekommendation för BACOWR

| Scenario | Välj |
|----------|------|
| **Maximal kontroll, determinism, stateful gates** | LangGraph |
| **Tydlig rollmodell, "crew" mental model** | CrewAI |
| **Snabb experimentell parallisering, minimal overhead** | Swarms |

**Konkret för BACOWR:**  
- **Starta med LangGraph** om du vill ha full kontroll över när Research slutar och Content börjar, och när QA failar → Remediation loop.  
- **Välj CrewAI** om du föredrar att definiera "Research Crew" och "Content Crew" med tydliga roller (Researcher, Writer, Editor).  
- **Swarms** passar om du vill testa subagent-delegation snabbt — coordinator skapar Preflight Worker, SERP Worker etc. dynamiskt.

---

## 4. Kritiska designregler

### 4.1 Gemensam state i filer (filesystem memory)

**Problem:** Agent-chat-state är volatil och svår att återanvända mellan sessioner.  
**Lösning:** All state ska vara filbaserad:
- `preflights/job_NNN.json`
- `blueprints/job_NNN_prompt.md`
- `articles/job_NN.md`
- `batch_state.json` (senaste fas per jobb)

Inga agenter får lita på implicit konversationsminne. Allt läses/skrivs till disk.

### 4.2 Single writer rule

Endast en agent får skriva en viss artefaktklass:
- Preflights: Research Agent (eller Preflight Worker)
- Blueprints: Content Agent (eller Blueprint Worker)
- Artiklar: Content Agent (Draft Writer / Remediation Writer)

Undvik race conditions genom att aldrig ha två agenter som skriver till samma fil.

### 4.3 QA är hård gate

Innan nästa jobb startar: nuvarande artikel måste ha 11/11 PASS. Ingen undantag.

### 4.4 Schema-validering

Alla agent-outputs valideras mot JSON-schema innan de används av nästa agent.

### 4.5 Timeout + retry-policy

Varje agent-anrop ska ha:
- Timeout (t.ex. 120 s för SERP)
- Retry (max 2 om transient fel)
- Explicit fail om validering misslyckas

---

## 5. Implementation — Faser

### Fas 1: Basorkestrering (1–2 dagar)

- [ ] Sätt upp huvudagenter (2 eller 3) med message contracts
- [ ] Filkontrakt oförändrade: `preflights/`, `blueprints/`, `articles/`
- [ ] Enkel sekvens: Research → Content (→ QA om separat)
- [ ] Verifiera att ett enda jobb går igenom

### Fas 2: Agentisering av Research (2–3 dagar)

- [ ] Flytta preflight + metadata + SERP till Research-sidan
- [ ] Subagenter (om ramverk stödjer): Preflight Worker, Metadata Worker, SERP Probe Worker, Trustlink Worker
- [ ] Spara all evidens per jobb (SERP snippets, trustlink-kandidater)
- [ ] Evidence Verifier: validera att trustlinks är djuplänkar (ej target/publisher)

### Fas 3: Agentisering av Content + QA (2–3 dagar)

- [ ] Writing-agent genererar draft från blueprint
- [ ] QA-agent validerar via `article_validator.py`
- [ ] Remediation-loop: om QA failar, Remediation Writer får specifika fixar (t.ex. "flytta anchor till ord 350")
- [ ] Max 3 remediation-försök per artikel

### Fas 4: Benchmark mot baseline (1 dag)

- [ ] Jämför: token per jobb, tid per jobb, QA first-pass rate, antal omskrivningar
- [ ] Dokumentera i `experimental/multiagent/benchmark_results.md`

---

## 6. Mätpunkter (måste loggas)

| Mått | Beskrivning | Var logga |
|------|-------------|-----------|
| Tid per jobb | Sekunder från jobb-start till artikel klar | `batch_metrics.json` |
| QA first-pass rate | Andel artiklar som passerar 11/11 på första försök | Samma |
| Antal QA-fix-loopar | Remediation-försök per artikel | Samma |
| Fel per fas/agent | Vilken agent/fas som failade | `error_log.json` |
| Token per jobb | Totala tokens (input + output) per jobb | Samma eller LangSmith |

---

## 7. Ramverk-specifika noteringar

### LangGraph

- **StateGraph** med noder: `load_jobs` → `research` → `content` → `qa` → `remediate` (conditional) → `content` (loop) eller `done`
- **Checkpointer** för resume (men BACOWR använder filer — överväg fil-baserad state)
- **Human-in-the-loop** node för metadata/SERP om agent körs externt
- Dokumentation: https://langchain-ai.github.io/langgraph/

### CrewAI

- **Hierarchical Process**: Manager Agent (Research Supervisor) med `manager_llm` delegating till Researcher, Metadata Fetcher, SERP Analyst
- **allow_delegation=True** för peer-to-peer
- **Task** med dependencies: Research Task → Writing Task → QA Task
- Dokumentation: https://docs.crewai.com/

### Swarms

- **Agent** med `selected_tools` inkl. `create_sub_agent`, `assign_task`
- **max_loops="auto"** för sub-agent delegation
- Coordinator skapar Preflight Worker, SERP Worker etc. on-the-fly
- Dokumentation: https://docs.swarms.ai/

---

## 8. Viktiga lösningar och gotchas

### 8.1 web_search / web_fetch är externa

BACOWR kräver `web_search` och `web_fetch` — dessa körs oftast av Cursor/IDE-agenten, inte av Python-kod. Lösning:
- Exponera ett API eller CLI som tar emot SERP-resultat. Multiagent-systemet anropar detta (eller en mock under utveckling).
- Eller: en "hybrid" där Research Supervisor är en Cursor-agent med instruktion att köra web_search och skriva resultat till fil. Python-orchestrator läser filen och fortsätter.

### 8.2 Kontextstorlek per agent

Subagenter får begränsad kontext. Skicka bara det som behövs:
- SERP Worker: preflight + probe queries (inte hela batch)
- Draft Writer: blueprint prompt + SYSTEM.md (inte SERP-raw)

### 8.3 Svenska språket

Alla agenter måste veta att artiklar ska vara på svenska (om inte publisher är engelskspråkig). Inkludera i system prompts.

### 8.4 SYSTEM.md som delad referens

Artikelregler (750–900 ord, anchor 250–550, etc.) måste vara tillgängliga för både Writer och QA-agent. Använd samma `SYSTEM.md` som i core.

### 8.5 Handoff mellan agenter

Tydlig handoff-format:
- Research → Content: "Preflight enriched, target_intent ready, trustlinks selected. Se preflights/job_NNN.json."
- Content → QA: "Article written. Se articles/job_NN.md."
- QA → Remediation: "Check X failed: [specific fix]."

---

## 9. Definition of Done

- [ ] Minst 1 batch med 5+ jobb körd via multiagent-flöde
- [ ] Stabil QA-pass-rate på nivå med eller bättre än baseline (solo-agent)
- [ ] Inga kontraktsbrott mellan agentfaser (schema-validering passerar)
- [ ] Benchmark-dokumentation med token, tid, first-pass rate

---

## 10. Filstruktur (förslag)

```
experimental/
├── core/                    # pipeline, engine, models, validator
├── plans/                   # denna fil + skillified-plan
└── multiagent/              # ny mapp för multiagent-implementation
    ├── agents/
    │   ├── research_supervisor.py   # eller .yaml för CrewAI
    │   ├── content_supervisor.py
    │   └── qa_supervisor.py         # om 3 agenter
    ├── workers/             # subagent-definitioner
    ├── state/               # batch_state.json, etc.
    ├── graph.py             # LangGraph StateGraph (om LangGraph)
    ├── crew.py              # CrewAI Crew (om CrewAI)
    └── README.md
```

---

*Skapad 2026-02-20 för återkomst efter sjukhusvistelse.*
