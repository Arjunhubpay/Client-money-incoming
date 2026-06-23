# Fund-Flow Pattern Detector — MCP + Claude + Notion path

This implements the **MCP → Claude → Notion** route for the *Fund Flow Pattern
Detector* handover brief (Towsif Rahman). It replaces the original
`fund-flow-alerts-n8n.json` → Slack workflow with:

```
Hubpay platform MCP   ->   Claude (detector engine)   ->   Notion review queue
 (query-analytics)         pattern strength scoring         Fund-Flow Findings DB
 aggregated, non-regulated  + attribution (separate axis)   one page per finding
```

Claude is the runtime: it calls the `query-analytics` MCP tool, runs the
detector in this repo over the result, and writes findings to Notion via
`notion-create-pages`. The repo holds the **logic** (testable, source-agnostic);
the MCP servers provide the **I/O**.

## The architectural decision (why v2 exists)

v1 used `min(inbound_conf, outbound_conf)`, which conflated *"how strong is this
pattern"* with *"how sure are we which bank this is"*. On AED-to-AED flows the
IBAN prefix is usually ambiguous, so v1 silently suppressed real patterns.

v2 scores two **independent** axes (`fundflow/scoring.py`,
`fundflow/attribution.py`):

| Axis | Built from | Notes |
|------|-----------|-------|
| `patternStrength` (0–100) | recurrence (saturates at 6 cycles) + amount consistency (1 − CV) + interval regularity (1 − CV) | The only thing that decides Fire/Silent |
| `attributionConfidence` (0–100) | how deterministically the provider/corridor can be named from metadata | **Never** lowers `patternStrength` |

Providers are reported as labelled-but-uncertain strings (`"Zand or NBF"`) with
a `providerInferenceMethod` field — never collapsed into the pattern score.

## Two profiles, one engine

- **`compliance`** (`fundflow/compliance.py`) — the original use: pairs inbound↔
  outbound per client within ±7 days / ±5% amount, fires at `patternStrength ≥ 70`.
  Validated against the four synthetic clients from §3 of the brief.
- **`commercial`** (`fundflow/commercial.py`) — the **Option A** non-regulated
  reframe: scores per-account FX corridors from aggregated analytics to spot
  **forward-contract candidates** (recurring, sizeable, regular FX flows). Reuses
  the identical scoring engine.

## Governance boundary (important)

This path runs **Option A only** — aggregated commercial intelligence from the
analytics layer. `fundflow/sources/analytics_mcp.py` reads account name +
corridor + count + amount + date. It does **not** read beneficiary names, IBANs,
or per-transaction personal data.

> **Option B (live transaction monitoring) is out of scope here.** Per §6 of the
> brief, pointing this detector at regulated per-client transaction data turns
> its output into regulated artefacts and requires **Compliance / MLRO sign-off**
> before it can run. Do not extend `analytics_mcp.py` to pull regulated fields
> without that sign-off.

## Layout

```
fundflow/
  scoring.py            shared pattern-strength primitives (the v2 core)
  attribution.py        provider/corridor inference — the separate axis
  models.py             Transaction, FxFlow, Finding
  compliance.py         inbound<->outbound conduit detector  (Fire at >=70)
  commercial.py         Option-A forward-contract opportunity scorer
  sources/
    synthetic.py        the 4 brief validation clients (fixtures)
    analytics_mcp.py    Option-A adapter: query-analytics -> FxFlow + the MCP query
  sinks/
    notion.py           Finding -> Notion page payloads + the database DDL
  fixtures/
    analytics_pull_sample.json   a real Option-A pull (captured 2026-06-23)
  run.py                CLI orchestrator (mirrors the live Claude flow offline)
tests/
  test_detector_v2.py   asserts Fire/Silent/fxInvolved behaviours of the 4 clients
```

## Run it

```bash
# 1. Validate the detector against the four synthetic clients (no network)
python tests/test_detector_v2.py

# 2. Compliance findings for the synthetic clients
python -m fundflow.run synthetic

# 3. Commercial (Option A) findings from a saved analytics pull
python -m fundflow.run commercial --pull fundflow/fixtures/analytics_pull_sample.json
```

### Live operation (what Claude does each run)

1. **Pull** — call `query-analytics` (cube `TreasurySettlementDetail`, measures
   `count` + `total_send_amount`, dims `account_name`/`account_type`/`send_currency`/
   `receive_currency`, time dim `ordered_at` day granularity, `last 90 days`).
   The exact query is documented in `fundflow/sources/analytics_mcp.py`.
2. **Normalize** — `analytics_mcp.normalize(rows)` → `FxFlow[]`.
3. **Detect** — `commercial.detect(flows)` → `Finding[]`.
4. **Write** — `notion.build_pages(findings)` → `notion-create-pages` into the
   *Fund-Flow Findings — Review Queue* database
   (data source `9e3767ce-24bb-49b8-9373-91b683e5c47d`).

The Notion database was created once from `notion.CREATE_TABLE_DDL`.

## Notion review queue

Each finding becomes one page with: Subject, Profile, Status (Fire/Silent),
Pattern Score, Attribution + Attr. Conf. + Attr. Method (the separate axis),
FX Involved, Cycles, Review Status (New/Reviewed/Dismissed/Escalated) and a
Summary, with the full scoring breakdown + evidence in the page body. Reviewers
triage via the Review Status column.

## Status & limitations (carried from the brief)

This is a **starting point**, not a deployable system. Still not done: live
beneficiary/IBAN extraction into one record, MLRO review/sign-off, a
false-positive review process, an alert → SAR escalation path, reporting
access-control policy, and threshold tuning against real data. The synthetic
strengths here run higher than the brief's 87/88 because the fixtures are
deliberately clean — the tests assert the **behaviours** (Fire/Silent,
fxInvolved, attribution independence), which is the contract that matters.
