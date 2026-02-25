You are the execution orchestrator for this repo. Work silently and do NOT message me during execution. Only respond once you are completely finished AND all required output artifacts are created/updated. If anything is blocked (missing permission / missing file / ambiguous run command), stop immediately and output a single BLOCKER summary at the end.

AUTOPERMISSIONS (assume granted unless the tool requires an explicit confirmation):
- Read/write all files in the repo root
- Create new markdown files in repo root
- Execute local, non-network commands (python, tests, grep/rg, ls/tree, git status/diff)
- NO network calls unless explicitly required for inventory (default: NO)

PARALLELISM:
- If your environment supports parallel sub-agents or parallel task execution, spawn as many as reasonable to run independent analyses simultaneously (inventory, hard-values concordance, bypass surface mapping, 8-phase state mapping, degraded-mode mapping).

CONTEXT:
This is an existing system (12 files, non-trivial). Swedish SEO article generation pipeline operated by an AI agent.
Treat as INTEGRATION. Do not restructure. Keep all files flat in root.

PRIMARY RISKS TO ANSWER:
1) Can the agent bypass pipeline→engine integration (as in v6.1)?
2) Do all 12 files agree on every hard value (word count, anchor position, trustlinks, headings, bullets)?
3) Is the 8-phase execution flow complete (handoffs + failure states defined)?
4) Weakest points: what breaks first under pressure?
5) Does engine blueprint output actually constrain the agent to SYSTEM.md rules?
6) Degraded mode (missing aiohttp/bs4): safe or silently compromises quality?
7) Any unnecessary complexity removable without weakening constraints?

REQUIRED OUTPUT (write these files in repo root):
A) INVENTORY_REPORT.md
   Must include:
   - Full root file list + responsibilities map (authoritative source for which constraint)
   - Canonical run command(s): how to run end-to-end
   - pipeline→engine call graph + explicit bypass surfaces list
   - Hard Values Concordance table: each hard value → where declared/enforced in each file (✅/❌ + notes)
   - 8-phase flow state model: phases, entry/exit conditions, required artifacts, failure states, gates
   - Degraded-mode behavior mapping: what changes when aiohttp/bs4 missing, and which quality controls are impacted
   - Evidence plan: what artifacts/logs prove “pipeline used” vs “agent went solo”

B) (Optional but preferred if you can do it deterministically from code+docs without guessing)
   PROOF_PLAN.md
   - Concrete proof hooks / commands to validate bypass detection, hard-values compliance, QA template enforcement, and degraded-mode policy.

RULES:
- Do not change any code unless absolutely necessary for inventory instrumentation, and only if you can do it as minimal diffs; otherwise keep read-only.
- Never “assume” hard values—extract them from authoritative files and code paths.
- If something conflicts (e.g., word count differs between files), record it as a conflict with exact locations.

STOP CONDITION:
- If you cannot determine the canonical run command or where outputs are emitted, include it as the top blocker in INVENTORY_REPORT.md with the exact missing info needed.

When complete, output ONE final message that contains:
- A short checklist confirming the required sections exist in INVENTORY_REPORT.md
- A list of any conflicts discovered (hard value drift / bypass surfaces / undefined flow states)
- The exact paths of the files you produced.
