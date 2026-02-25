# BACOWR Experimental Workspace

Detta är en portabel kopia av kärnfiler för att testa alternativa arkitekturer i en annan IDE/agentmiljö. Förberett för återkomst — alla filer och planer finns på plats.

---

## Innehåll

| Mapp/Fil | Beskrivning |
|----------|-------------|
| **core/** | Runtimefiler (pipeline, engine, models, validator), agentfiler (SKILL.md, CLAUDE.md), runbooks, tester |
| **plans/** | Utförliga experimentplaner och teknikguide |
| **plans/plan_skillified_pipeline.md** | Plan A: Pipeline-steg som separata skills |
| **plans/plan_multiagent_architecture.md** | Plan B: Multiagent med 2–3 huvudagenter + subagenter |
| **plans/TECHNIQUES_GUIDE.md** | Snabbreferens: LangChain, LangGraph, CrewAI, Swarms |
| **plans/PREFLIGHT_DB_ARCHITECTURE_SPEC.md** | Preflight-databas: arkitekturspec för kund-för-kund byggande från länkplanering + historisk länkdatabas (~6k länkar) |
| **plans/ULTIMATE_PREFLIGHT_SERVER_VISION.md** | Vision för Cursor extension + MCP + full pipeline. Input till uLTmA Planner (flowmap.html) |
| **plans/BRIDGE_INTERPRETER_SPEC.md** | Kontextlänksinterpreter: SERP + publisher → vilka källor semantiskt bäst stärker target TA (verkshöjd) |

---

## Två experiment

### Experiment A: Skillifierad pipeline
Bryt ut faserna till separata skills med tydliga JSON-kontrakt. Rekommenderad start: lättviktig approach (inget tungt ramverk). Se `plans/plan_skillified_pipeline.md`.

### Experiment B: Multiagent-arkitektur
2–3 huvudagenter (Research, Content, QA) med upp till 5 subagenter vardera. Rekommenderade ramverk: **LangGraph** (kontroll) eller **CrewAI** (rollmodell). Se `plans/plan_multiagent_architecture.md`.

---

## Snabbstart vid återkomst

1. **Öppna `experimental/core/`** som projekt (eller hela `experimental/`).
2. **Installera dependencies:**
   ```
   pip install -r core/requirements.txt
   ```
3. **Kör verifieringsgates:**
   ```
   cd core && python smoke_test.py && python integration_test.py
   ```
4. **Läs planerna** i `plans/` innan du sätter igång.
5. **Välj approach:**
   - Skillifierad → börja med `plans/plan_skillified_pipeline.md` Fas 1
   - Multiagent → läs `plans/TECHNIQUES_GUIDE.md`, välj LangGraph/CrewAI/Swarms, följ `plan_multiagent_architecture.md`

---

## Viktigt

- **SYSTEM.md** är source of truth för artikelregler.
- **engine.py** och **pipeline.py** används fortfarande tillsammans (inte ersatta av experimenten).
- Batch-scripten (`batch_preflight.py`, `batch_blueprint.py`) är ett extra lager ovanpå kärnflödet.
- Alla kärnfiler är synkade från projektroten (2026-02-20).

---

## Filstruktur (översikt)

```
experimental/
├── README.md              ← du läser denna
├── core/                  ← körbara filer
│   ├── pipeline.py, engine.py, models.py, article_validator.py
│   ├── batch_preflight.py, batch_blueprint.py
│   ├── integration_test.py, smoke_test.py
│   ├── SYSTEM.md, RUNBOOK.md, BATCH_RUNBOOK.md
│   ├── .cursor/skills/     ← bacowr-preflight, bacowr-serp-research, bacowr-article-qa
│   └── tests/
└── plans/
    ├── plan_skillified_pipeline.md
    ├── plan_multiagent_architecture.md
    └── TECHNIQUES_GUIDE.md
```

---

*Uppdaterad 2026-02-20. Förberett för implementation vid återkomst.*
