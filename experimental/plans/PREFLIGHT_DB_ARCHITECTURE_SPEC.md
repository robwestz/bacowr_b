# Preflight Database Architecture — Specifikation för Claude Opus

> **Syfte**: Detaljerad specifikation för arkitekten som ska designa hela databaslösningen för BACOWR preflight-databasifiering.  
> **Läsare**: Claude Opus (eller annan vass modell) som ska implementera arkitekturen.  
> **Input**: Två datakällor — länkplaneringsspreadsheets och historisk länkdatabas (~6000 länkar).  
> **Output**: En design som gör det möjligt att bygga preflight-databasen inkrementellt, kund för kund, med stöd för semantisk analys.

---

## Exekutiv sammanfattning (TL;DR)

| Aspekt | Beslut |
|--------|--------|
| **Data källa 1** | LÄNKAR KUNDER 2025 — D=Domain (publisher), E=Targeting URL (target), F=Anchor. Operativ planering. Header-mappning konfigurerbar. |
| **Data källa 2** | Main länksheet — ~6000 länkar. C=kund, D=published_url→publisher, E=target_url. Filtrera `status=Live`. |
| **Partitionering** | Kund-för-kund (kund_canonical). Bygger DB inkrementellt, men publisher/target lagras globalt (dedup). |
| **Lagring** | Rekommendation: Hybrid — SQLite för links/kunder, JSON-filer för berikad publisher/target (agentkonsumtion). |
| **Semantisk bonus** | 6000 länkar = publisher→target-matrix, anchor-mönster, topical overlap. Kräver links-tabell + möjlighet till aggregationer. |

---

## 1. Kontext och mål

### 1.1 Vad preflight-databasen ska tillhandahålla

- **Publisher-profil** per domän: vad sidan handlar om (primary_topics, confidence), agentoptimerat format
- **Target-profil** per URL: entiteter, sökfrågor, sökintention, ideal_bridge_direction (från SERP-analys)
- **Friska data** så att BACOWR-jobb kan starta med båda polerna redan kända — uppgiften blir endast att hitta den semantiska bryggan

### 1.2 Två datakällor som ska matas in

| Källa | URL | Innehåll | Storlek |
|-------|-----|----------|---------|
| **LÄNKAR KUNDER** | [Spreadsheet](https://docs.google.com/spreadsheets/d/1VHeHz4DB3r1XjpE21Qe3o-dC1jK9m26HnhJb_yiw6Is/edit?usp=sharing) | Operativ länkplanering, kommande och pågående jobb | Varierar per månad |
| **Main länksheet** | [Spreadsheet](https://docs.google.com/spreadsheets/d/1yYRYU1BP-Lx3Mv1rYBLt6LgogIVYOJTctpRTLeqwEcc/edit?usp=sharing) | Historik över alla publicerade länkar, alla kunder | ~6000 länkar |

### 1.3 Affärslogik

- Endast **aktiva kunder** ska inkluderas
- Bygga databasen **kund för kund** — prioritering och inkrementell påbyggnad
- Utnyttja historisk länkdatabas för **semantisk analys** (vilka publisher→target-kombinationer som använts, mönster i ankare, etc.)
- **Ingen duplicering** — samma publisher/target berikas endast en gång globalt

---

## 2. Kolumnmappning — Exakt specifikation

### 2.1 LÄNKAR KUNDER 2025 (länkplanering)

Header-rad (typiskt): `Writer | MKT | Budget | Domain | IsCustomer / Targeting URL | Anchor | Topic | Content | ...`

| Kolumn | Header | Innehåll | Användning i preflight | Exempel |
|--------|--------|----------|------------------------|---------|
| **D** | Domain | Publisher-domän (var länken publiceras) | Publisher-berikning | alingsastidning.se, hn.se, ttela.se |
| **E** | IsCustomer / Targeting URL | Target-URL (kundens sida som länkas till) | Target-berikning | https://happycasino.se/, https://bethard.com/sv/betting |
| **F** | Anchor | Ankartext | Metadata för jobb | happy casino, live casino med HD-streaming |

**OBS**: Kolumnindex kan skifta mellan flikar/versioner (t.ex. om Budget eller MKT kolumner tas bort). Arkitekten bör stödja header-namn-baserad mappning: `Domain`→publisher, `IsCustomer`/`Targeting URL`/`target_url`→target, `Anchor`→anchor.

**Normalisering**:
- Publisher: ta bort `www.`, normalisera till lowercase
- Target: validera URL, fixa `https:/` → `https://`
- Tomma rader, rubrikrader: hoppa över

### 2.2 Main länksheet (historisk länkdatabas)

| Kolumn | Header | Innehåll | Användning | Exempel |
|--------|--------|----------|------------|---------|
| **C** | kund_canonical_url | Kundens kanoniska domän (ägare av målsidan) | Kundpartitionering, aktiva-kunder-filter | haxan.se, chronos.se, blugiallo.com |
| **D** | published_article_exact_url | Exakt URL till artikeln/layouten som innehåller länken | **Publisher** — extrahera domän för profilering | https://medialvagledning.com/2022/08/25/... |
| **E** | target_url | Exakt URL till kundens sida som länkas till | **Target** — SERP-berikning | https://haxan.se/, https://chronos.se/diabetes/blodsocker |
| **F** | link_type | Typ av placement | Filtrering (t.ex. endast Artikel) | Artikel, Startsida, Partner |
| **G** | market_language | Språk/marknad | Metadata, språkval vid berikning | SE, ENG |
| **H** | anchor_text | Ankartext | Semantisk analys, jobb-metadata | Städprodukter, Diabetes typ 2 |
| **I** | status | Länkstatus | Filtrering — endast Live | Live, Removed |
| **J** | publishing_date | Publiceringsdatum | Semantisk analys, tidsfiltrering | 2022-09-02 |

**Publisher-extraktion** från `published_article_exact_url`:
- Parsa URL → extrahera host (t.ex. `medialvagledning.com`, `focusera.se`)
- Normalisera: lowercase, ta bort `www.`

**Target**: använd `target_url` direkt (kan vara startsida eller undersida).

**Kund-canonical** (`kund_canonical_url`): används för att partitionera och filtrera till aktiva kunder. Detta är inte samma som target — kund är "ägaren", target är den specifika sidan.

---

## 3. Entitetsmodell

### 3.1 Publisher

En **publisher** är en domän som publicerar innehåll. Profileras en gång, återanvänds över alla kunder.

```
Publisher
├── domain: str              # t.ex. ttela.se, hn.se
├── primary_topics: List[str]
├── confidence: float
├── language: str            # sv, en (heuristik från domain/market)
├── enriched_at: datetime
└── source_rows: int         # antal länkar som använt denna publisher (optional, för prioritet)
```

### 3.2 Target

En **target** är en URL (kundens sida) som ska få backlinks. SERP-analyseras en gång per URL.

```
Target
├── url: str                 # exakt URL
├── url_normalized: str       # för dedup (canonical form)
├── title: str               # meta title (hämtad)
├── meta_description: str
├── core_entities: List[str]
├── cluster_entities: List[str]
├── lsi_terms: List[str]
├── ideal_bridge_direction: str
├── search_intent_summary: str
├── probes_completed: int
├── enriched_at: datetime
├── kund_canonical: str      # vilken kund äger denna target (för partitionering)
└── source_rows: int         # antal länkar till denna target (optional)
```

### 3.3 Link (registrerad placement)

En **link** representerar en faktisk eller planerad placement: publisher + target + anchor.

```
Link
├── publisher_domain: str
├── target_url: str
├── anchor_text: str
├── link_type: str           # Artikel, Startsida, Partner
├── market_language: str
├── status: str              # Live, Removed, Planed
├── publishing_date: date   # optional
├── kund_canonical: str
├── source: str              # "lankar_kunder" | "main_lanksheet"
└── source_row_id: str       # för spårbarhet
```

### 3.4 Kund (aggregat)

En **kund** är en logisk gruppering baserat på `kund_canonical_url`. Används för partitionering.

```
Kund
├── canonical_url: str        # t.ex. haxan.se
├── is_active: bool          # från extern lista eller heuristik
├── link_count: int
├── unique_publishers: int
├── unique_targets: int
└── last_publishing_date: date
```

---

## 4. Arkitekturfråga: Lagring och partitionering

### 4.1 Krav

1. **Global deduplicering**: Samma publisher/target berikas endast en gång
2. **Kund-för-kund processing**: Möjlighet att köra "berika allt för kund X" först
3. **Inkrementell påbyggnad**: Nya länkar (från planeringssheet eller historik) ska kunna läggas till utan omkörning av hela databasen
4. **Semantisk analys**: Data ska kunna användas för mönsteranalys (publisher→target, anchor-mönster)
5. **Agentoptimerat format**: Output ska vara lätt att läsa in i BACOWR-agenten (JSON med exakt de fält som behövs)

### 4.2 Alternativ A: Platta JSON-filer

```
preflight_db/
├── publishers/
│   ├── ttela.se.json
│   ├── hn.se.json
│   └── manifest.json          # lista över alla + enriched_at
├── targets/
│   ├── {url_hash}.json
│   └── manifest.json
├── links/
│   ├── by_kund/
│   │   ├── haxan.se.json      # alla länkar för kund haxan
│   │   └── chronos.se.json
│   └── manifest.json
└── kund_index.json            # aktiva kunder, link_count per kund
```

**Fördelar**: Enkelt, inget DB, versioneringsvänligt  
**Nackdelar**: Ingen SQL-fråga, måste skanna filer för semantisk analys

### 4.3 Alternativ B: SQLite

```
Tables:
- publishers (domain PK, primary_topics JSON, confidence, enriched_at)
- targets (url PK, url_normalized, title, meta_description, core_entities JSON, ...)
- links (id PK, publisher_domain FK, target_url FK, anchor_text, kund_canonical, status, ...)
- kunder (canonical_url PK, is_active, link_count, ...)
```

**Fördelar**: Frågor, joins, semantisk analys via SQL  
**Nackdelar**: Kräver SQLite, lite mer setup

### 4.4 Alternativ C: Hybrid

- **SQLite** för links, kunder, och index (snabb lookup, semantisk analys)
- **JSON-filer** för publisher/target-berikning (BACOWR vill ha dem som filer, enkel inläsning)

### 4.5 Rekommendation

**Alternativ C (Hybrid)** — SQLite för operativ data och analys, JSON för berikad data som agenten konsumerar.

---

## 5. Processing — Kund-för-kund

### 5.1 Inmatning från Main länksheet

1. **Läs CSV/export** av Main länksheet
2. **Filtrera**:
   - `status == "Live"`
   - `kund_canonical` finns i lista över aktiva kunder (extern fil eller parametrar)
3. **Extrahera unika**:
   - Publishers: domän från `published_article_exact_url`
   - Targets: `target_url` (normaliserad)
4. **Bygg kund-index**: gruppera länkar per `kund_canonical`, räkna länkar
5. **Sortera kunder**: t.ex. efter `link_count` (störst först) eller manuell prioritet

### 5.2 Inmatning från LÄNKAR KUNDER

1. **Läs CSV/export** med kolumnmappning E→publisher, F→target, G→anchor
2. **Skapa länkar** med `source="lankar_kunder"`, `status="Planned"`
3. **Kund**: kan härledas från target-URL:s domän (t.ex. bethard.com från target bethard.com/sv)

### 5.3 Kund-för-kund körning

```
För varje kund K (i prioritetsordning):
  links_K = alla länkar där kund_canonical == K
  
  För varje unik publisher P i links_K:
    Om P INTE finns i preflight_db/publishers/:
      Profilera P (PublisherProfiler)
      Spara till publishers/P.json
    (Annars: skip)
  
  För varje unik target T i links_K:
    Om T INTE finns i preflight_db/targets/:
      Hämta metadata (web_fetch eller web_search)
      Kör SERP-probes (TargetIntentAnalyzer)
      Spara till targets/{hash}.json
    (Annars: skip)
  
  Uppdatera kund-status: K processed
```

**Viktigt**: Publisher och target lagras globalt. Kund-partitioneringen styr bara **vilka länkar vi processar** och **i vilken ordning** — inte var data lagras.

### 5.4 Merge av LÄNKAR KUNDER

När planeringsdata läggs till:
- Nya länkar läggs till i `links`
- Nya publishers/targets som inte finns berikas
- Befintliga återanvänds

---

## 6. Semantisk analys — Möjligheter

Med ~6000 historiska länkar får vi:

### 6.1 Publisher→Target-matrix

- Vilka publisher-domäner har länkat till vilka target-domäner/URL:er
- Frekvens per par
- Kan användas för att prioritera eller för att "lära" vilka bryggor som fungerat

### 6.2 Anchor-mönster

- Per target-URL: vilka ankare använts
- Per publisher: vilka ankare de tenderar att acceptera (om vi har flera länkar till samma publisher)
- Kan validera att föreslagen anchor ligger i acceptabelt intervall

### 6.3 Topical overlap

- Publisher primary_topics vs target core_entities
- Historiskt: vilka topic–entity-kombinationer har lett till Live-länkar
- Kan förbättra bridge-scoring i engine

### 6.4 Lagring för semantisk analys

- **Links-tabellen** (SQLite) med publisher, target, anchor, kund, status, datum
- **Aggregerade vyer** (materialiserade eller views): publisher_target_pairs, anchor_per_target, etc.
- **Export till JSON** om agenten behöver "exempel på vad som fungerat" som kontext

---

## 7. Format för agentoptimerad berikning

### 7.1 Publisher JSON (per domän)

```json
{
  "domain": "ttela.se",
  "primary_topics": ["lokala nyheter", "Västra Götaland", "sport", "kultur"],
  "confidence": 0.85,
  "language": "sv",
  "enriched_at": "2026-02-20T12:00:00Z"
}
```

**Utelämna** allt som agenten inte behöver för bridge-beräkning.

### 7.2 Target JSON (per URL)

```json
{
  "url": "https://www.bethard.com/sv/betting",
  "title": "Sportbetting och spel - Bethard",
  "meta_description": "...",
  "core_entities": ["sportbetting", "Bethard", "odds", "live betting"],
  "cluster_entities": ["fotboll", "ishockey", "tennis", "casino"],
  "lsi_terms": ["vadslagning", "spelbolag", "bonus"],
  "ideal_bridge_direction": "Connect sports/live events to betting offers",
  "search_intent_summary": "Commercial/informational mix - users comparing bookmakers",
  "probes_completed": 5,
  "enriched_at": "2026-02-20T12:05:00Z"
}
```

**Kompatibilitet**: Ska mappa 1:1 till det som `TargetIntentAnalyzer` och `create_blueprint_from_pipeline` förväntar sig (eller en enkel transform).

---

## 8. Öppna designfrågor för arkitekten

1. **Aktiva kunder**: Hur definieras de? Extern CSV, manuell lista, eller heuristik (t.ex. minst 1 Live-länk senaste 12 månaderna)?

2. **Google Sheets API vs CSV-export**: Ska systemet läsa direkt från Sheets (kräver API-nyckel) eller förvänta CSV-export? CSV är enklare för första iterationen.

3. **Metadata för target**: Target-berikning kräver title + meta_description. `batch_preflight` idag får detta via aiohttp (web_fetch) eller agent-patch. Preflight-maskinen behöver samma — web_fetch i batch, eller agent-in-the-loop per target?

4. **SERP-probes**: Kräver web_search × 5 per target. Sker det i samma process som preflight-maskinen (med web_search-tool) eller ska det vara en separat fas där agenten kör sökningar och matar tillbaka?

5. **Uppdateringsfrekvens**: Hur ofta ska befintliga publisher/target-profilers uppdateras? SERP ändras över tid. Förslag: `enriched_at` + policy (t.ex. "om >90 dagar, re-berika vid nästa jobb").

6. **Felhantering**: Target-URL som inte nås (404, timeout). Ska den markeras som `failed`, sparas för retry, eller ignoreras?

7. **Rate limiting**: Vid många web_fetch/web_search — throttling, parallellitet?

---

## 9. Definition of Done för arkitekten

Arkitekturen är klar när följande finns specificerat:

- [ ] **Lagringsformat**: Exakt schema för publishers, targets, links, kunder (tabeller/filer)
- [ ] **Kolumnmappning**: Konfigurerbar mapping för båda datakällorna (header-namn + kolumnindex-fallback)
- [ ] **Processing pipeline**: Steg-för-steg från CSV-import till berikad DB, inkl. kund-partitionering
- [ ] **Deduplicering**: Hur publishers/targets hanteras globalt vid kund-för-kund körning
- [ ] **Integration med BACOWR**: Hur ett jobb (publisher X, target Y) hämtar data från preflight-DB istället för att köra preflight live
- [ ] **Semantisk analys**: Vilka tabeller/vyer/export som behövs för framtida mönsteranalys

---

## 10. Referenser

| Dokument | Syfte |
|----------|-------|
| `RUNBOOK.md` | Befintlig BACOWR-flöde |
| `batch_preflight.py` | Nuvarande batch-preflight, JSON-kontrakt |
| `pipeline.py` | PublisherProfiler, TargetAnalyzer, SemanticEngine |
| `engine.py` | TargetIntentAnalyzer, build_research_plan_from_metadata |
| `FLOWMAP.md` | Datamodeller (Preflight, TargetIntentProfile) |

---

*Spec skapad 2026-02-20. Optimerad för Claude Opus som arkitekt.*  
*Uppdatera vid nya krav eller datakällor.*
