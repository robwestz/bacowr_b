# BACOWR QA TEMPLATE (Deterministic, 11 checks)

Run this after each article is written to disk.

Command (article_validator API):
```python
from pathlib import Path
from article_validator import validate_article

article_path = "articles/job_01.md"
article_text = Path(article_path).read_text(encoding="utf-8")

result = validate_article(
    article_text=article_text,
    anchor_text="<anchor_text>",
    target_url="<target_url>",
    publisher_domain="<publisher_domain>",
    language="<sv|en>",
    serp_entities=[...],  # optional list from probe results
)

passed = sum(1 for c in result.checks if c.passed)
print(f"QA: {passed}/{len(result.checks)}")
for check in result.checks:
    print(check.name, check.passed, check.value, check.expected)
```

Checks (must all pass):
1) Word count 750-900
2) Anchor text exact (>=1 match)
3) Anchor count = 1 (exact text + target URL)
4) Anchor position 250-550
5) Trustlinks (1-2, before anchor, not target/publisher domain)
6) No bullets/lists
7) Headings <= 1
8) Forbidden phrases = 0
9) Language check (sv/en)
10) SERP entities >= 4
11) Paragraphs >= 4
