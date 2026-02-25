# BACOWR v6.2 — Batch Operator Runbook

Kort körguide för batchflödet med befintliga scripts.

## 0) Förberedelser

- Jobbfil i CSV-format med kolumner: `job_number,publication_domain,target_page,anchor_text`
- Projektroot: kör alla kommandon från samma katalog som `pipeline.py`

## 1) Batch preflight (Fas 1-4)

```bash
python batch_preflight.py jobs.csv --output-dir preflights
```

Output:
- `preflights/job_NNN.json` per jobb
- `preflights/batch_manifest.json`

## 2) Metadata patch (om behövs)

För jobb med `status = needs_metadata`:
- hämta target metadata (title + meta_description) via web_fetch/web_search
- skriv tillbaka i `preflights/job_NNN.json` under `preflight.target`

## 3) SERP research (agentstyrt)

Per jobb:
- använd probes i `preflights/job_NNN.json` (5 st)
- kör web_search för varje probe och mata tillbaka resultat
- uppdatera jobbfilen så `target_intent`/`probes` har `probes_completed >= 3`

## 4) Batch blueprint + promptfiler

```bash
python batch_blueprint.py preflights --output-dir blueprints
```

Output:
- `blueprints/job_NNN_blueprint.json`
- `blueprints/job_NNN_prompt.md`
- `blueprints/batch_ready.json`

## 5) Skriv artiklar

Per `job_NNN_prompt.md`:
- skriv artikel till `articles/job_NN.md`
- följ `SYSTEM.md` (750-900 ord, exakt 1 ankarlänk, trustlinks 1-2 före ankarlänk, inga listor, max 1 heading)

## 6) QA (11/11 krävs)

Kör validering med `article_validator.py`-API eller befintlig QA-rutin enligt `qa-template.md`.
Alla 11 checks måste passera innan nästa jobb.

## 7) Slutgate

```bash
python integration_test.py
```

Förväntat: `INTEGRATION TEST PASSED`
