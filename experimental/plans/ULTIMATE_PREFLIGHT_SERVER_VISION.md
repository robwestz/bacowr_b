# Ultimate Preflight Server — Vision & Systembeschreibung

> **Syfte**: Input till uLTmA Planner. Använd detta dokument när du säger:  
> *"Plan a system: [innehållet i denna fil]"*  
> 
> **Mål**: Cursor extension med webview som hub för att servera BACOWR-agenten med preflight-data.  
> **North star**: 100 länkartiklar på en förmiddag.

---

## 1. Vision (2–3 meningar)

**Ultimate Preflight Server** är en Cursor IDE-extension med inbäddad webview-panel som visar preflight-databasen (kunder, publishers, targets, länkar) och låter användaren peka, välja och säga till agenten "kör preflight för den här kunden". Extensionen är hubben: den exponerar databasen visuellt, anropar CLI/MCP för åtgärder, och integrerar med BACOWR-artikelpipelinen. Genom att förberäkna publisher/target-profilering och cache:a SERP-data minskar systemet varje jobbs overhead till nästan enbart "hitta bryggan + skriv" — vilket möjliggör 100 artiklar på en förmiddag med rätt orchestration.

---

## 2. Vad systemet ska göra (verb/aktioner)

- **Visa** databasen: kunder, publishers, targets, länkar i en bläddringsbar panel
- **Importera** CSV från Main länksheet och LÄNKAR KUNDER
- **Aktivera** kunder (manuell fil eller heuristik)
- **Berika** publishers (profilering) och targets (metadata + SERP) i batch
- **Exportera** berikad data per kund
- **Köra** batch_preflight med --use-db för att använda cachad data
- **Köra** batch_blueprint för att generera skrivprompts
- **Skicka** kontext till agenten (t.ex. "jobben för denna kund")
- **Fråga** semantisk analys (publisher→target-matrix, anchor-mönster)
- **Trigga** åtgärder från panelen: "Enrich denna kund", "Exportera", "Kör preflight för valda"
- **Visa** progress och status för pågående jobb
- **Hantera** fel (failed targets, retry, markera permanent failed)

---

## 3. Moduler (föreslagen decomposition)

| ID | Modul | Ansvar | Befintlig kod |
|----|-------|--------|----------------|
| M-01 | **Preflight DB** | SQLite + JSON-lagring, import/export, dedup, staleness | preflight_db/db.py, importer.py |
| M-02 | **Enricher** | Publisher-profilering, target-metadata, SERP (om implementerat) | preflight_db/enricher.py |
| M-03 | **CLI** | Alla preflight_db-kommandon | preflight_db/cli.py |
| M-04 | **MCP Server** | Exponera DB som verktyg åt agent | Ny |
| M-05 | **Cursor Extension** | Webview-panel, UI, åtgärdsknappar | Ny |
| M-06 | **BACOWR Integration** | batch_preflight --use-db, batch_blueprint | batch_preflight.py |
| M-07 | **Dashboard Generator** | Skapa live markdown/JSON för synlig status | Ny eller script |
| M-08 | **Kund Activator** | Aktivera/inaktivera kunder | preflight_db/kund_activator.py |

---

## 4. Teknikstack

| Lager | Teknik |
|-------|--------|
| **Extension** | TypeScript, VS Code Extension API, Webview API |
| **Webview UI** | HTML/CSS/JS (eller React om föredraget) |
| **Backend / DB** | Python 3.10+, SQLite, befintlig preflight_db |
| **Orchestration** | Extension anropar Python via CLI eller Node child_process |
| **Agent-kommunikation** | MCP (Model Context Protocol) eller extension-exponerade kommandon |

---

## 5. Dataflöde (ASCII)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CURSOR EXTENSION (M-05)                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  Webview Panel                                                           │ │
│  │  • Kundlista | Publisher-lista | Target-lista | Länk-tabell              │ │
│  │  • Välj kund → "Kör preflight för denna" → anropar MCP eller CLI         │ │
│  │  • Status, progress, fel                                                 │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────┬────────────────────────────────┬─────────────────────┘
                       │                                │
                       ▼                                ▼
┌──────────────────────────────────────┐   ┌──────────────────────────────────┐
│  MCP Server (M-04)                    │   │  CLI (M-03)                     │
│  • list_customers()                    │   │  import, activate, enrich,       │
│  • get_customer_detail(kund)          │   │  status, export, semantic        │
│  • run_enrichment(kund)                │   │  → anropas av extension eller   │
│  • run_preflight_batch(kund, jobs)     │   │  direkt av användaren            │
└──────────────────────┬────────────────┘   └────────────────┬─────────────────┘
                       │                                      │
                       └──────────────────┬───────────────────┘
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Preflight DB (M-01)                                                         │
│  • preflight.db (SQLite): kunder, publishers, targets, links                  │
│  • publishers/*.json, targets/*.json (agentoptimerat)                         │
│  • _manifest.json per mapp                                                    │
└──────────────────────┬──────────────────────────────────────────────────────┘
                       │
         ┌─────────────┼─────────────┬─────────────────┐
         ▼             ▼             ▼                 ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐
│ Enricher    │ │ BACOWR      │ │ Importer    │ │ Kund Activator      │
│ (M-02)      │ │ Integration │ │ (del av     │ │ (M-08)              │
│             │ │ (M-06)      │ │  M-01)      │ │                     │
│ Publisher   │ │ batch_      │ │ CSV →       │ │ activate --from-file│
│ Target      │ │ preflight   │ │ links,      │ │ activate --heuristic│
│ SERP        │ │ --use-db    │ │ stubs       │ │                     │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────────────┘
         │             │
         └─────────────┴──────────────────────→ batch_blueprint
                                               → articles/
```

---

## 6. Gränssnittskontrakt (översikt)

### Extension ↔ Backend (Python)

- **Anrop**: Extension → `child_process.spawn('python', ['-m', 'preflight_db.cli', ...])` eller MCP-klient
- **Retur**: JSON eller text som parsas i webview
- **Alternativ**: MCP-server som extension kan anropa (om Cursor har MCP-klient)

### Extension ↔ Agent (Cursor Chat)

- **Kontext**: Extension kan skicka vald kund/jobb till chatten (t.ex. via copy-paste eller API om tillgängligt)
- **Åtgärder**: Användaren säger "kör preflight för haxan" → agent har skill/regel som anropar CLI eller MCP

### MCP Server (om byggd)

- **Verktyg**: list_customers, get_customer_detail, run_enrichment, run_preflight_batch, export_customer
- **Input/Output**: JSON-typer som matchar preflight_db

---

## 7. Cursor Extension — detaljerad spec

### 7.1 Panel-layout

- **Sidofält-ikon**: Öppnar "Preflight Server"-panelen
- **Flikar eller sektioner**:
  - **Kunder**: Lista med kund (domän), link_count, enriched%, status. Klicka → detalj
  - **Publishers**: Lista med domän, status (enriched/pending/failed)
  - **Targets**: Lista med URL, status (metadata/serp/pending)
  - **Länkar**: Filtrerbar tabell (kund, publisher, target, anchor, status)
- **Åtgärder** (kontextuella knappar):
  - "Importera CSV" → filväljare → `cli import`
  - "Aktivera kunder" → `cli activate --heuristic` eller fil
  - "Enrich vald kund" → `cli enrich --all --kund X`
  - "Enrich alla" → `cli enrich --all`
  - "Exportera kund" → `cli export --kund X`
  - "Kör batch preflight för kund" → skapa jobs.csv från links, kör batch_preflight --use-db
  - "Skicka till agent" → kopierar jobbkontext till clipboard eller trigger för agent

### 7.2 Real-time uppdatering

- Panel läser status vid öppning
- Knapp "Refresh" eller auto-refresh var N:e sekund när pågående jobb
- Progress för enrichment: polling av CLI-output eller loggfil

### 7.3 Felhantering

- Visa failed publishers/targets med retry-knapp
- Markera som permanent failed
- Loggvy för senaste körning

---

## 8. MCP Server — verktyg (detaljerat)

| Verktyg | Input | Output |
|---------|-------|--------|
| `preflight_list_customers` | (none) | `{customers: [{domain, link_count, unique_publishers, unique_targets, active}]}` |
| `preflight_get_customer` | `kund: string` | Kunddetaljer + länkar + enrichment-status |
| `preflight_get_status` | (none) | Sammanfattning (kunder, publishers, targets, links) |
| `preflight_run_import` | `path: string, source: "main_lanksheet"|"lankar_kunder"` | `{rows_inserted, rows_skipped}` |
| `preflight_run_activate` | `mode: "heuristic"|"file", path?: string` | `{active, inactive, total}` |
| `preflight_run_enrich` | `kund?: string, scope: "publishers"|"targets"|"all"` | `{enriched, failed, total}` |
| `preflight_run_export` | `kund: string, output_dir?: string` | `{path, job_count}` |
| `preflight_run_batch_preflight` | `kund: string, jobs_csv_path?: string` | `{preflights_generated, db_hits, live_fetches}` |

---

## 9. SERP-enrichment (saknat idag)

Specen kräver SERP som fas. Förslag:

- **Fas**: Efter target-metadata, före export/batch_preflight
- **Input**: Targets med `status=metadata_fetched`, title och description ifyllda
- **Process**: Kräver `web_search` × 5 per target — agent-in-the-loop eller extern script som tar emot SERP-resultat
- **Output**: `save_serp_enrichment(url, plan)` — core_entities, cluster_entities, ideal_bridge_direction
- **CLI**: `enrich --serp [--kund X]` — förbereder lista, anropar engine för probe-plan, agent/script kör web_search, matar tillbaka

---

## 10. Dashboard / Live-vy (alternativ till extension)

Om extension är för tung att börja med:

- **Script**: `python -m preflight_db.cli dashboard` eller separat script
- **Output**: `preflight_dashboard.md` eller `preflight_status.json`
- **Innehåll**: Kunder, publishers, targets med status. Uppdateras vid behov.
- **Användning**: Användaren håller filen öppen, säger till agenten "för den här kunden" med referens till synlig rad.

---

## 11. Batch-orchestration för 100 artiklar

För att nå 100 artiklar på en förmiddag:

1. **Pre-berikning**: Alla publishers och targets för valda kunder är redan enriched (kör kvällen innan eller i bakgrunden)
2. **Jobs-CSV**: Genereras från `export --kund X` eller direkt från links-tabellen
3. **batch_preflight --use-db**: 100% cache-träff om allt är berikat → snabbt
4. **batch_blueprint**: Genererar 100 prompter
5. **Artikelproduktion**: Agent eller multi-agent skriver 100 artiklar parallellt eller i hög genomströmning
6. **QA**: validate_article per artikel, fix-loop vid behov

Flaskhalsar: SERP (om ej pre-berikad), artikelskrivning (mest tidskrävande), QA-fix-loopar.

---

## 12. Befintlig kod som återanvänds

| Komponent | Sökväg | Roll |
|-----------|--------|------|
| PreflightDB | preflight_db/db.py | Kärna |
| Importer | preflight_db/importer.py | CSV → DB |
| Enricher | preflight_db/enricher.py | Publisher + target metadata |
| Kund Activator | preflight_db/kund_activator.py | Aktiva kunder |
| CLI | preflight_db/cli.py | Alla kommandon |
| batch_preflight | batch_preflight.py | Med --use-db |
| batch_blueprint | batch_blueprint.py | Prompter |
| pipeline, engine, models | pipeline.py, engine.py, models.py | BACOWR-kärna |

---

## 13. Constraints

- **Cursor/VS Code**: Extension måste fungera i Cursor (VS Code-kompatibel)
- **Python**: Backend är Python — extension anropar via CLI eller MCP
- **Ingen extern server**: Allt körs lokalt (SQLite, filer)
- **Befintlig preflight_db**: Ska inte brytas — extension/MCP bygger ovanpå
- **Web search**: SERP kräver extern web_search (agent eller API) — kan inte köras helt i isolation

---

## 14. Prioritering (implementation order)

| Fas | Moduler | Mål |
|-----|---------|-----|
| 1 | M-04 (MCP) | Agent har DB-verktyg, kan lista och köra utan extension |
| 2 | M-07 (Dashboard) | Enkel live-vy som markdown/JSON |
| 3 | M-05 (Extension) | Webview-panel med kundlista, åtgärder |
| 4 | SERP i M-02 | Full enrichment-pipeline |
| 5 | Batch-orchestration | Optimera 100-artikel-flöde |

---

## 15. Success metrics

- **Preflight cache hit rate**: >90% vid batch_preflight --use-db
- **Tid per artikel** (med cache): <2 min från jobb till färdig artikel (exkl. skrivtid)
- **100 artiklar**: Genomförbara på en förmiddag med förberedd DB och parallell skrivning
- **Extension UX**: Användaren kan bläddra databasen och trigga "enrich denna kund" utan att öppna terminal

---

## 16. Upp till planeraren

När du använder uLTmA:

1. **Öppna** `C:\Users\robin\Downloads\ultima-planner101\` i Cursor
2. **Läs** SKILL.md, workflows/plan-system.md
3. **Säg**: "Plan a system: [klistra in eller referera till denna fil]"
4. **Agenten** producerar: Architecture DNA, modulmanifest, kontrakt, koherenstester, exekveringsordning
5. **Validera** med `python scripts/validate_plan.py`
6. **Använd** flowmap.html för att visualisera den slutgiltiga planen

---

*Skapad 2026-02-20. Redo för uLTmA plan-system workflow.*
