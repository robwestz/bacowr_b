# BACOWR — Zero-Context Agent Load Order

> **Syfte**: Denna fil är startpunkten för en agent utan tidigare kontext.
> Läs denna fil först, sedan följ läsordningen nedan.

---

## 1. Läsordning (före första jobbet)

Läs dessa filer **i denna ordning**:

| # | Fil | Syfte |
|---|-----|-------|
| 1 | **RUNBOOK.md** | Steg-för-steg exekvering, exakt Python-kod per fas |
| 2 | **SYSTEM.md** | Artikelregler: ordantal 750–900, anchor 250–550, trustlinks 1–2, stil |
| 3 | **SKILL.md** | Hard constraints (HC-1–HC-9), 8-fas flöde, filroller |
| 4 | **INIT.md** | Crash recovery, snabbstart, driftcheck |

**RUNBOOK.md** är exekveringsguiden. Följ den bokstavligt.  
**SYSTEM.md** är artikelreglerna. Alla hårda krav som artikeln måste uppfylla.

---

## 2. Exekveringsgate (innan första jobbet)

Efter att du läst filerna ovan, producera denna bekräftelse:

```
EXECUTION CONFIRMATION
══════════════════════
Jag har läst RUNBOOK.md och SYSTEM.md. Jag bekräftar:

STEG JAG KOMMER FÖLJA (per jobb, i ordning):
  Fas 2: asyncio.run(pipe.run_preflight(job))
  Fas 3: web_search → patcha preflight.target.title + .meta_description
  Fas 4: analyzer.build_research_plan_from_metadata()
  Fas 5: web_search × 5 probes → analyzer.analyze_probe_results() per probe
         trustlinks: analyzer.build_trustlink_queries() → web_search
  Fas 6: create_blueprint_from_pipeline() → bp.to_agent_prompt()
  Fas 7: Skriv artikel STRIKT efter bp.to_agent_prompt() + SYSTEM.md
  Fas 8: validate_article() → 11/11 PASS

JAG KOMMER INTE:
  ✗ Skapa egna Python-scripts eller tempfiler
  ✗ Skriva Python-kod till disk — ALL kod körs inline
  ✗ Hårdkoda SERP-data eller metadata
  ✗ Hitta på egna ämnen — engine väljer topic, inte jag
  ✗ Skriva artikeln fritt — jag följer bp.to_agent_prompt()
  ✗ Hoppa över steg eller "optimera" ordningen

PREFLIGHTS KÖRS I BATCH. ARTIKLAR SKRIVS EN I TAGET. ENGINE STYR.
```

**Invänta användarens godkännande** innan du kör något jobb.

---

## 3. Vid batchkörning

Om du kör batch (många jobb med scripts):

| Fil | Syfte |
|-----|-------|
| **BATCH_RUNBOOK.md** | Kort körguide: batch_preflight → metadata patch → SERP → batch_blueprint → skriv → QA |

---

## 4. Vid QA (efter varje artikel)

| Fil | Syfte |
|-----|-------|
| **qa-template.md** | 11-checks format, `article_validator`-API |

Alla 11 checks måste passera innan nästa jobb.

---

## 5. Snabbverifiering (rekommenderad före batch)

```bash
python smoke_test.py
python integration_test.py
```

Förväntat: `SMOKE TEST PASSED` och `INTEGRATION TEST PASSED`.

---

## 6. Filer du inte behöver läsa

- **engine.py, pipeline.py, models.py** — anropas via API:er som beskrivs i RUNBOOK.md
- **FLOWMAP.md** — valfri referens
- **README.md** — inte exekveringsguide

---

*BACOWR v6.3 — 2026-02-19*
