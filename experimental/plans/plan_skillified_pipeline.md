# Plan A — Skillifierad Pipeline (Utförlig)

> **Mål**: Bryt ut pipeline-steg till separata, körbara skills med tydliga kontrakt och gates.  
> **Status**: Redo för implementation vid återkomst.  
> **Baserat på**: BACOWR v6.2/v6.3 (2026-02-19)

---

## 1. Sammanfattning

| Aspekt | Beskrivning |
|--------|-------------|
| **Varför** | Enklare återstart (resume från fas N), bättre felsökning, lägre kognitiv last per agentkall, möjlighet att byta LLM per delsteg |
| **Ansats** | Varje fas blir en skill med definierat input/output och schema-validering |
| **Rekommenderad teknik** | Lättviktig approach först (JSON-kontrakt + befintlig kod). LangChain/LlamaIndex som optional layer |

---

## 2. Skill-mappning mot nuvarande 8-fas pipeline

### Nuvarande flöde (RUNBOOK.md / SKILL.md)

```
Fas 1: Load Jobs        → pipeline.load_jobs()
Fas 2: Preflight        → pipe.run_preflight() / run_batch_preflight()
Fas 3: Metadata patch   → agent web_search/web_fetch → patcha preflight.target
Fas 4: Probe generation → analyzer.build_research_plan_from_metadata()
Fas 5: SERP + trustlinks→ agent web_search × 5 + trustlink-queries → analyzer.analyze_probe_results()
Fas 6: Blueprint        → create_blueprint_from_pipeline() → bp.to_agent_prompt()
Fas 7: Article write    → agent skriver artikel enligt blueprint + SYSTEM.md
Fas 8: QA               → validate_article() → 11/11 PASS
```

### Föreslagen skill-uppdelning

| Skill | Input | Output | Motsvarar fas | Kräver agent? |
|-------|-------|--------|---------------|---------------|
| **skill-load-jobs** | `jobs.csv` | `jobs.json` eller normaliserad lista | Fas 1 | Nej |
| **skill-preflight-batch** | `jobs.json` / CSV | `preflights/job_NNN.json`, `batch_manifest.json` | Fas 2 | Nej |
| **skill-metadata-patch** | preflight med `needs_metadata` | patchad preflight (title, meta_description) | Fas 3 | **Ja** (web_search/web_fetch) |
| **skill-serp-research** | patchad preflight | `target_intent.json` med probes_completed, entities | Fas 4+5 | **Ja** (5× web_search + trustlinks) |
| **skill-blueprint-batch** | enriched preflights | `blueprints/job_NNN_prompt.md`, `batch_ready.json` | Fas 6 | Nej |
| **skill-article-write** | promptfil + SYSTEM.md | `articles/job_NN.md` | Fas 7 | **Ja** |
| **skill-article-qa** | artikel + job params | pass/fail + detaljerade fix-suggestions | Fas 8 | Nej (validator) eller Ja (remediering) |

**Notera:** Faser 4 och 5 kan slås ihop till en enda skill `skill-serp-research` eftersom de delar samma agent-anrop (web_search) och engine-anrop (analyzer).

---

## 3. Teknikval och ramverk

### Alternativ A: Lättviktig (rekommenderad start)

- **Ingen ny dependency** — använd befintlig `batch_preflight.py`, `batch_blueprint.py`, `engine.py`, `article_validator.py`
- **JSON-schema per skill-output** — validera med `jsonschema` eller `pydantic`
- **Skill = CLI-kommando eller Python-modul** med tydlig signatur
- **Orkestrering** = enkel loop eller shell-script som anropar skills i ordning

**Fördelar:** Snabbast att implementera, inget lock-in, full kontroll.  
**Nackdelar:** Resume/crash recovery måste byggas manuellt.

### Alternativ B: LangChain

- **LCEL (LangChain Expression Language)** för att kedja steg
- **RunnableSequence** eller **RunnableParallel** för batch-preflight
- **Output parsers** för strukturerad output per skill
- **Retries** inbyggda

**När det passar:** Om du vill ha retry-logik, fallback-chains, och observability (LangSmith) från början.  
**BACOWR-specifikt:** Fas 3 och 5 kräver `web_search` — LangChain har `Tool`-abstraktion men agenten (Cursor/annan IDE) kör ofta verktyget externt. Du får en "hybrid" där vissa steg är LangChain-noder och andra är "human/agent-in-the-loop".

### Alternativ C: LlamaIndex

- **Workflows** eller **Agentic Workflows** för pipeline
- **Bra om** du vill lägga till retrieval över `preflights/`, `blueprints/`, tidigare batch-historik
- **Document indexing** av gamla artiklar för "learn from past"-patterns

**När det passar:** Om du senare vill ha RAG över historiska jobb eller blueprint-arkiv.  
**BACOWR-specifikt:** Överkill för första iterationen — börja utan.

### Rekommendation

**Starta med Alternativ A.** Definiera JSON-schema först, wrappa befintlig kod, bygg resume-logik.  
**Väx till LangChain** om du behöver: retry-policies, komplex branching, eller LangSmith-tracing.

---

## 4. JSON-kontrakt (schema per skill)

### skill-load-jobs

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "array",
  "items": {
    "type": "object",
    "required": ["job_number", "publisher_domain", "target_url", "anchor_text"],
    "properties": {
      "job_number": { "type": "integer" },
      "publisher_domain": { "type": "string" },
      "target_url": { "type": "string", "format": "uri" },
      "anchor_text": { "type": "string" }
    }
  }
}
```

### skill-preflight-batch → batch_manifest.json

```json
{
  "batch_id": "string",
  "job_count": "integer",
  "jobs": [
    {
      "job_number": "integer",
      "status": "ready_for_serp | needs_metadata | failed",
      "preflight_path": "preflights/job_NNN.json"
    }
  ]
}
```

### skill-metadata-patch

Input: preflight-fil. Output: samma struktur med `target.title` och `target.meta_description` ifyllda.  
Validering: `target.title` får inte vara tom.

### skill-serp-research → target_intent

Output från `analyzer` (TargetIntentProfile) serialiseras. Obligatoriska fält:

- `probes_completed` ≥ 3
- `core_entities` (array, minst 2)
- `cluster_entities` (array)
- `trustlink_candidates` eller motsvarande

### skill-blueprint-batch → batch_ready.json

```json
{
  "ready_jobs": ["integer"],
  "prompt_paths": { "job_number": "blueprints/job_NNN_prompt.md" }
}
```

### skill-article-qa

Input: artikeltext, anchor_text, target_url, publisher_domain, language, serp_entities.  
Output: `{ "passed": bool, "checks": [...], "fix_suggestions": [...] }`.

---

## 5. Implementation — Faser

### Fas 1: Kontrakt först (1–2 dagar)

- [ ] Skapa `experimental/skillified/schemas/` med JSON-schema per skill
- [ ] Skriv `validate_output(skill_name, output)` som använder jsonschema
- [ ] Dokumentera vilka fält som är obligatoriska per skill

### Fas 2: Skill-wrapper runt befintlig kod (2–3 dagar)

- [ ] `skill_load_jobs`: wrapper kring `pipe.load_jobs()` → skriv `jobs.json`
- [ ] `skill_preflight_batch`: anropa `batch_preflight.py` eller `pipe.run_batch_preflight()`
- [ ] `skill_metadata_patch`: CLI som tar preflight-path, förväntar agent har patchat — eller **agent-in-loop** där agent får instruktion och skriver tillbaka
- [ ] `skill_serp_research`: anropa engine + kräver att agent matar in SERP-resultat (hybrid)
- [ ] `skill_blueprint_batch`: anropa `batch_blueprint.py`
- [ ] `skill_article_write`: instruktion till agent — ingen Python som skriver artikeln
- [ ] `skill_article_qa`: wrapper kring `validate_article()`

### Fas 3: Gate-orchestrering och resume (1–2 dagar)

- [ ] `orchestrator.py` eller shell-script som:
  - Läser `batch_state.json` (senaste lyckade fas per jobb)
  - Kör nästa skill för jobb som inte är klara
  - Vid fel: skriv `failed_jobs.json` med felmeddelande, stoppa batch
- [ ] Resume: starta om från `batch_state.json`

### Fas 4: Observability (valfritt)

- [ ] Körlogg per jobb: `logs/job_NNN.log`
- [ ] Batch-metrics: pass rate, vanligaste QA-fel, tid per fas

---

## 6. Viktiga lösningar och gotchas

### 6.1 Agent-in-the-loop skills (metadata, SERP, article write)

Dessa kräver att en agent (Cursor, Codex, etc.) kör `web_search` eller skriver text. Lösning:

- **skill-metadata-patch**: Output en `metadata_tasks.json` med jobb som behöver patchas. Agent löser dem, skriver tillbaka till `preflights/job_NNN.json`. Orchestrator väntar på att filerna uppdaterats.
- **skill-serp-research**: Engine genererar queries. Agent kör web_search. En "serp_runner.py" kan ta emot agentens resultat via stdin eller fil och mata tillbaka till engine.
- **skill-article-write**: Agent får prompt-fil som input. Ingen automatisk skrivning — agent måste skriva till `articles/job_NN.md`.

### 6.2 För grova vs för många skills

- **För grova skills** → tillbaka till monolit. Om en skill gör för mycket (t.ex. preflight + metadata + SERP) försvinner fördelarna.
- **För många skills** → orkestrering blir dyr. 10+ skills ger overhead utan tydlig win. Behåll 6–7 skills.

### 6.3 Drift utan schema-validering

**Problem:** Tysta kontraktsbrott — en skill skriver fel format, nästa kraschar eller ger fel resultat.  
**Lösning:** Validera varje skill-output mot schema innan nästa körs. Fail fast.

### 6.4 Sökvägar och working directory

- Alla sökvägar ska vara **absoluta** eller **relativa till projektroot**. Agenten (CLAUDE.md) föredrar `C:/` paths.
- `batch_preflight.py` och `batch_blueprint.py` förväntar sig `--output-dir`. Se till att experimental-miljön har konsekvent `preflights/`, `blueprints/`, `articles/`.

### 6.5 Integration test

- `integration_test.py` måste fortfarande passera. Skills ska använda samma pipeline/engine-moduler — inte duplicerad logik.

---

## 7. Definition of Done

- [ ] Varje fas körbar fristående (manuellt eller via orchestrator)
- [ ] Resume fungerar från mitten av batch (t.ex. batch_state.json säger "job 3 klar med serp, job 4 behöver metadata")
- [ ] `integration_test.py` pass
- [ ] Minst 1 real batch med stabil QA-pass-rate dokumenterad
- [ ] README i `experimental/skillified/` med körinstruktioner

---

## 8. Filstruktur (förslag)

```
experimental/
├── core/                    # befintlig — pipeline, engine, models, validator
├── plans/                   # denna fil + multiagent-plan
└── skillified/             # ny mapp för skill-implementation
    ├── schemas/
    │   ├── jobs.json
    │   ├── batch_manifest.json
    │   └── ...
    ├── skills/
    │   ├── load_jobs.py
    │   ├── preflight_batch.py
    │   ├── metadata_patch.py   # eller .md med instruktion
    │   ├── serp_research.py
    │   ├── blueprint_batch.py
    │   ├── article_write.md    # instruktion till agent
    │   └── article_qa.py
    ├── orchestrator.py
    └── README.md
```

---

*Skapad 2026-02-20 för återkomst efter sjukhusvistelse.*
