# Preflight DB — Utvärdering mot arkitekturspecifikationen

> **Datum**: 2026-02-20  
> **Spec**: `PREFLIGHT_DB_ARCHITECTURE_SPEC.md`  
> **Implementation**: `preflight_db/` + `batch_preflight.py` (--use-db)

---

## Definition of Done (Spec sektion 9)

### [x] Lagringsformat

**Status: PASS**

SQLite-schemat matchar spec 3–4:
- **4 tabeller**: `kunder`, `publishers`, `targets`, `links` ✓
- **Index**: `idx_links_kund`, `idx_links_publisher`, `idx_links_target`, `idx_links_status`, `idx_targets_kund`, `idx_targets_status`, `idx_publishers_status`, `idx_links_dedup` ✓
- **Views**: `v_publisher_target_matrix`, `v_kund_summary`, `v_anchor_patterns`, `v_publisher_topic_reach` ✓
- **Hybrid**: JSON-filer i `publishers/` och `targets/` med `_manifest.json` ✓

Schema har fler fält än spec (t.ex. `site_name`, `category_structure`, `status`, `retry_count`) — det är utökat, inte avvikande.

---

### [x] Kolumnmappning

**Status: PASS**

Importer stödjer flexibel header-namn-mappning för båda datakällorna:
- **Main länksheet**: `MAIN_LANKSHEET_MAPPING` i `importer.py` med kandidater för `kund_canonical`, `published_url`, `target_url`, `anchor_text`, `link_type`, `market_language`, `status`, `publishing_date` ✓
- **LÄNKAR KUNDER**: `LANKAR_KUNDER_MAPPING` med kandidater för `publisher_domain` (Domain, domain, publisher), `target_url` (IsCustomer / Targeting URL, Targeting URL, etc.), `anchor_text` (Anchor, anchor) ✓
- **Case-insensitive match**: `_resolve_column()` använder `lower()` ✓
- **Delimiter-auto**: `,`, `|`, `\t` ✓

**Anmärkning**: `config.yaml` innehåller `column_mappings` men laddas aldrig. Importer använder hårdkodade dict i `importer.py`. Konfigurerbar mapping via YAML är alltså inte implementerad — men den faktiska mappningen täcker spec-kraven.

---

### [~] Processing pipeline

**Status: DELVIS**

Spec 5.3 listar 6 faser:
1. Import (CSV → links, stubs) — **JA**
2. Aktivering (aktiva kunder) — **JA**
3. Publisher-berikning — **JA**
4. Target-metadata — **JA**
5. **SERP-probes** — **NEJ** (ej implementerad)
6. Export — **JA** (via `export --kund`)

**SERP-fas saknas**:
- `db.save_serp_enrichment()` och `db.get_targets_needing_serp()` finns
- Ingen `enrich_serp()` i `enricher.py`, ingen `--serp` i CLI
- SERP kräver `web_search` × 5 per target — spec 8.4 antar agent-in-the-loop eller separat process. Implementationen har valt att inte bygga SERP-enrichment i batch-enricher (antagligen medvetet, eftersom web_search är extern)

---

### [x] Deduplicering

**Status: PASS**

- **Publisher**: `upsert_publisher_stub` med `ON CONFLICT DO NOTHING` — en rad per domän ✓
- **Target**: `upsert_target_stub` med `ON CONFLICT DO NOTHING` ✓
- **Links**: `UNIQUE(publisher_domain, target_url, anchor_text, source, source_row_hash)` + `insert_link` returnerar `False` vid duplicat ✓
- **Kund-för-kund**: `get_publishers_needing_enrichment(kund=X)` och `get_targets_needing_metadata(kund=X)` filtrerar på kund, men publishers/targets lagras globalt ✓

---

### [x] Integration med BACOWR

**Status: PASS**

- `batch_preflight.py --use-db` anropar `_run_with_db()` ✓
- `db.get_preflight(publisher_domain, target_url, anchor_text)` returnerar `Preflight` med publisher, target, bridge (om båda finns) ✓
- Vid cache-träff: använder DB-data, hoppar över live preflight ✓
- Vid cache-miss: kör live preflight och sparar till DB ✓
- Staleness: `db.is_stale("target", url)` — endast target kontrolleras; publisher TTL används inte i `_run_with_db` (mindre kritisk, 90 dagar)

---

### [x] Semantisk analys

**Status: PASS**

- **v_publisher_target_matrix**: publisher → target, link_count, anchors_used, first/latest ✓
- **v_anchor_patterns**: target_url, anchor_text, times_used, publishers_used_on ✓
- **v_kund_summary**: per kund, total_links, unique_publishers, unique_targets, live_links ✓
- **v_publisher_topic_reach**: publisher + primary_topics + kunder_served, targets_linked ✓
- **CLI**: `semantic --matrix`, `--anchors <url>`, `--kund-summary`, `--publisher-reach` ✓

---

## Öppna frågor (Spec sektion 8) — status

| # | Fråga | Beslut i implementation |
|---|-------|-------------------------|
| 1 | **Aktiva kunder** | CSV-fil (`--from-file`) ELLER heuristik (Live-länk senaste 12 mån) ✓ |
| 2 | **Google Sheets vs CSV** | CSV-export — ingen Sheets-API ✓ |
| 3 | **Metadata för target** | `TargetAnalyzer` (aiohttp) i batch — ingen agent-in-the-loop ✓ |
| 4 | **SERP-probes** | Ej implementerad i enricher. DB stödjer det; SERP antas köras separat (agent eller annat script) ⚠ |
| 5 | **Uppdateringsfrekvens** | TTL i config: publisher 90d, target metadata 30d, SERP 14d ✓ |
| 6 | **Felhantering** | `mark_publisher_failed` / `mark_target_failed`, retry_count, `permanently_failed` vid 404 ✓ |
| 7 | **Rate limiting** | `DomainRateLimiter` 1.5 s/domän, `max_concurrent=5` ✓ |
| +1 | *(implicit)* **SERP i batch?** | Nej — kräver web_search som är externt. Designval: SERP körs agent-driven eller separat |

---

## Saknat kritiskt

1. **SERP-enrichment i pipeline**  
   Spec 5.3: "Target-berikning" inkluderar SERP. DB och schema stödjer det, men ingen CLI/enricher-fas kör det. Det är det tydligaste gapet.

2. **config.yaml används inte**  
   `PreflightDBConfig` har hårdkodade värden. `config.yaml` är dokumentation, inte runtime-konfiguration. Mindre kritiskt men kan vara förvirrande.

3. **Publisher-staleness i _run_with_db**  
   Endast target kontrolleras. Om publisher är >90 dagar gammal används den ändå. Kan ge något föråldrad preflight.

---

## Potentiella buggar och designbrister

### 1. `_run_with_db` staleness-logik (minor)

```python
if cached and not db.is_stale("target", job.target_url):
```

- Kontrollerar inte `is_stale("publisher", ...)`.
- `get_preflight` returnerar `None` om varken pub eller tgt finns; men om båda finns och target är fresh men publisher stale, används cached ändå.

**Rekommendation**: Lägg till `and not db.is_stale("publisher", job.publisher_domain)`.

### 2. `get_preflight` kräver minst en av pub/tgt

```python
if not pub and not tgt:
    return None
```

- Om vi har t.ex. bara target men inte publisher returneras en Preflight med `publisher=None`. `_run_with_db` skulle då få en ofullständig preflight. Koden i `_run_with_db` kollar `cached` — en Preflight med `publisher=None` kan vara oanvändbar för blueprint.
- Spec: "båda polerna redan kända". Design: fallback till live om något saknas är rimligt. Men `get_preflight` returnerar redan när endast en pol finns — det kan ge halv-cachad preflight som batch_preflight fortfarande försöker använda.

**Rekommendation**: I `get_preflight`, returnera `None` om inte BÅDE pub och tgt finns (om full preflight krävs). Eller dokumentera att partial preflight accepteras.

### 3. `activate_heuristic` SQLite date-syntax

```python
AND publishing_date >= date('now', ? || ' months')
```
Med `("-12",)` → `date('now', '-12 months')`. Korrekt för SQLite ✓

### 4. Race conditions

- En enda `PreflightDB`-instans används per process. SQLite med WAL hanterar concurrent reads/writes.
- `DomainRateLimiter` med `asyncio.Lock` — korrekt för concurrent enrichment.

### 5. Links UNIQUE och `source_row_hash`

- `source_row_hash = _row_hash(publisher_domain, target_url, anchor_text, source)` — ingen radspecifik id.
- Två identiska rader (samma pub, target, anchor, source) ger samma hash → en enda link sparas. Det är avsiktlig dedup och stämmer med spec.

### 6. Foreign keys

- `links.publisher_domain REFERENCES publishers(domain)` — publishers skapas via `upsert_publisher_stub` före `insert_link` ✓
- `links.target_url REFERENCES targets(url)` — likadant ✓
- `links.kund_canonical REFERENCES kunder(canonical_domain)` — `upsert_kund` körs före insert ✓

---

## CLI-verifiering

```
$ python -m preflight_db.cli status
Preflight Database Status
==================================================
  Kunder Total: 4
  Kunder Active: 2
  ...

$ python -m preflight_db.cli --help
usage: python.exe -m preflight_db.cli [-h] [--db-dir DB_DIR]
                                      {import,activate,enrich,status,export,semantic} ...
```

**Resultat**: CLI fungerar ✓

---

## Sammanfattande poäng

| Kriterium | Poäng |
|-----------|-------|
| Lagringsformat | ✅ Fullt |
| Kolumnmappning | ✅ Fullt |
| Processing pipeline | ⚠️ 5/6 faser (SERP saknas) |
| Deduplicering | ✅ Fullt |
| Integration BACOWR | ✅ Fullt |
| Semantisk analys | ✅ Fullt |
| Öppna frågor | ✅ 7/8 besvarade (SERP designval) |

**Slutsats**: Implementationen följer spec mycket väl. Det viktigaste saknade är SERP-enrichment som körbar fas (databasen är förberedd). Rekommendation: Antingen lägg till en `enrich --serp` som förbereder targets och anropar en agent/script för web_search, eller dokumentera tydligt att SERP körs utanför preflight_db (t.ex. i batch_preflight eller manuellt).

---

*Utvärdering utförd 2026-02-20*
