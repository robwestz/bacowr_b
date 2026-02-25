# Bridge Interpreter — Specifikation

> **Syfte:** En interpreter som tolkar SERP-research + publisher-kunskap och fastslår vilka källor som semantiskt bäst stärker target URLs topical authority (TA). Output: konkret sökspecifikation + vägledning för agenten — särskilt för texter med höga kvalitetskrav (verkshöjd).

---

## 1. Referensartikel (målnivå)

Exempel som visar vad "rätt" betyder:
`022_videoslots_oddsmatcher_varför-oddsmatchning-kräver-matematik-inte.md`

| Källa | Roll | Varför den stärker TA |
|-------|------|------------------------|
| **Spelinspektionen** (djuplänk statistik) | Marknadskontext | Svensk licensierad spelmarknad, 6.7 mkr omsättning — binder "oddsmatchning" till regulerad sportbetting |
| **PMC/NCBI** (akademisk studie) | Vetenskaplig grund | Kelly-kriteriet, prediktion, medianvärde — binder "matematik" till value betting |
| **Videoslots** | Ankarlänk | Sitter i kontext som redan etablerat entiteter från båda trustlänkarna |

**Insikt:** Trustlänkarna fyller olika **slots** — marknad vs forskning. Båda binder publisher (sport/odds) → target (sportbetting) via SERP-bekräftade entiteter (oddsmatchning, value bet, Kelly).

---

## 2. Nuvarande begränsning

### Pipeline (SemanticEngine._trust_link_topics)

```python
def _trust_link_topics(self, pub, target) -> List[str]:
    return pub.primary_topics[:3] + ["statistik", "forskning"]
```

- Alltid samma mönster: publisher-topics + "statistik" + "forskning"
- Ingen koppling till SERP-entiteter eller ideal_bridge_direction
- Ingen roll- eller typdifferentiering (regulator vs akademi vs branschrapport)

### Engine (build_trustlink_queries)

```python
queries.append(f"{t} rapport forskning")  # t = trust_link_topic
```

- Enkel strängkonkatenering
- Ingen tolkning av vad som *semantiskt bäst* stärker TA
- Ingen koppling till meta_desc_predicate, core_entities, cluster_entities

### Select_trustlinks

- Filtrerar: target, publisher, avoid, non-deeplink
- Poäng: topic-overlap + deeplink-bonus
- **Saknas:** Huruvida källan faktiskt *stärker TA* för de entiteter target söker ranka för

---

## 3. Bridge Interpreter — Översikt

**Input:**
- `TargetIntentProfile` (SERP: core_entities, cluster_entities, ideal_bridge_direction, meta_desc_predicate)
- `PublisherProfile` (primary_topics, site_description)
- `SemanticBridge` (trust_link_topics, trust_link_avoid, distance_category)
- `TargetFingerprint` (title, main_keywords — optional)

**Output:**
- **BridgeSpec** — strukturerad specifikation av vad agenten ska hitta
- **Sökqueries** — konkreta web_search-frågor per slot
- **Agentvägledning** — människoläsbar instruktion

---

## 4. Data-struktur: BridgeSpec

```python
@dataclass
class SourceSlot:
    """En 'slot' som en trustlink ska fylla — vad den semantiskt bidrar med."""
    role: str              # "market_context" | "academic_foundation" | "industry_report" | "bridge_concept"
    source_type: str       # "authority|regulator" | "research|study" | "industry" | "general"
    topics: List[str]       # Vad källan ska handla om (från publisher + SERP)
    entities: List[str]    # SERP-entiteter som källan bör bekräfta/stärka
    search_query: str      # Konkret web_search-fråga
    rationale: str          # Varför denna slot stärker target TA


@dataclass
class BridgeSpec:
    """Output från Bridge Interpreter — vad agenten ska hitta."""
    slots: List[SourceSlot]           # 1–2 slots beroende på semantic distance
    combined_queries: List[str]       # Deduplicerade queries för web_search
    agent_guidance: str               # Människoläsbar: "Hitta 1–2 källor: (a) ..., (b) ..."
    trust_topics: List[str]            # Bakåtkompatibelt med select_trustlinks
    avoid_domains: List[str]          # Från SemanticBridge
```

---

## 5. Interpreter-logik (konceptuell)

### Steg 1: Bestäm antal slots

- **Close/Identical** (publisher och target överlappar): 1 slot räcker
- **Moderate/Distant**: 2 slots — en som binder publisher→gap, en som binder gap→target
- **Unrelated**: 2 slots obligatoriskt (annars känns ankarlänken forcerad)

### Steg 2: Kategorisera source types utifrån vertikal

| Target-vertikal | Rekommenderade source-typer |
|-----------------|-----------------------------|
| casino, betting, spel | regulator (Spelinspektionen), akademisk forskning (PMC, arXiv) |
| e-handel, produkter | branschrapport, konsumentorganisation, Boverket/standard |
| tjänster, B2B | branschrapport, statistikmyndighet, forskning |
| livsstil, mode | redaktionell källa, trendrapport |

### Steg 3: Bygg topics per slot från SERP + publisher

**Slot 1 (marknad/kontext):**
- Kombinera: publisher primary_topics + core_entities + "statistik" eller "rapport" eller "reglering"
- Exempel: `["spelmarknad", "licensierad", "Sverige", "kvartalsstatistik"]`

**Slot 2 (forskning/evidens):**
- Kombinera: meta_desc_predicate eller head_entity + cluster_entities + "studie" eller "forskning"
- Exempel: `["Kelly", "prediktion", "value bet", "akademisk"]`

### Steg 4: Generera queries

- **Idag:** `"{topic} rapport forskning"` (generiskt)
- **Ny:** Per slot: `"{topic1} {topic2} {source_type_hint}"`
  - Slot 1: `"spelinspektionen spelmarknad statistik Sverige"`
  - Slot 2: `"Kelly criterion prediction study sport betting"`

### Steg 5: Agentvägledning

Människoläsbar text som agenten får:
```
Hitta 1–2 källor som stärker målsidans TA för "oddsmatchning" och "sportbetting":
(a) Auktoritet/regulator på den svenska licensierade spelmarknaden — t.ex. statistik, kvartalsrapport.
(b) Akademisk forskning om prediktion, value betting eller Kelly-kriteriet — t.ex. peer-reviewade studier.
Båda ska vara djuplänkar. Undvik: spelbolag, affiliatesajter, target/publisher-domäner.
```

---

## 6. Integration med befintlig kod

### Filer att skapa

| Fil | Ansvar |
|-----|--------|
| `bridge_interpreter.py` | `BridgeInterpreter`-klass, `SourceSlot`, `BridgeSpec` |
| `engine.py` (ändring) | `build_trustlink_queries` anropar `BridgeInterpreter.interpret()` istället för egen logik, eller bridge_interpreter används av batch_blueprint/agent-prompt |

### Flöde

```
SERP (plan) + Preflight (publisher, bridge) 
    → BridgeInterpreter.interpret()
    → BridgeSpec (slots, queries, guidance)
    → Agent kör web_search(spec.combined_queries)
    → select_trustlinks (nu med spec.trust_topics)
    → Agent väljer 1–2 källor utifrån spec.agent_guidance
```

### Bakåtkompatibilitet

- `BridgeSpec.trust_topics` fylls med samma typ av strängar som `SemanticBridge.trust_link_topics` — så `select_trustlinks` fungerar som idag
- `build_trustlink_queries` kan returnera `BridgeSpec.combined_queries` (eller bara queries som idag)
- Blueprint/AgentPromptRenderer kan få `spec.agent_guidance` som extra sektion

---

## 7. Implementation — föreslagen ordning

1. **bridge_interpreter.py** — ny fil
   - `SourceSlot`, `BridgeSpec`
   - `BridgeInterpreter.interpret(plan, preflight) -> BridgeSpec`
   - Vertikal → source_type mapping (hårdkodad tabell till en början)
   - Slot-by-slot topic-building från SERP + publisher

2. **Integrera i engine/batch**
   - `create_blueprint_from_pipeline` eller `AgentPromptRenderer`: anropa interpreter, inkludera `agent_guidance` i prompt
   - `build_trustlink_queries`: antingen delegera till interpreter eller läsa `BridgeSpec.combined_queries`

3. **Utvärdera**
   - Kör på 5–10 jobb, jämför outputs mot manuella bedömningar
   - Justera vertikal-mapping och topic-building utifrån resultat

---

## 8. Öppna frågor

- Ska **source-type** (regulator, research, industry) hämtas från vertikal-uppslag eller från SERP (t.ex. om probe 1–3 visar mycket .gov/.edu)?
- Ska **select_trustlinks** få en ny scoring-faktor: "överensstämmer med BridgeSpec.slots"?
- Ska interpreter vara **agent-agnostisk** (bara BridgeSpec) eller producera direkt prompt-text för Cursor/Claude?

---

*Dokument skapat 2026-02-20. Input: referensartikel, SYSTEM.md, engine.py, pipeline.py.*
