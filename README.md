# Client-money incoming — USD via Currency Cloud → out via Corpay

Scheduled report that finds **clients who receive USD into a Currency Cloud
account and then move it out via Corpay**, and publishes the list to a Notion
database for interactive filtering/sorting.

## What it computes

Condition:

- **A — USD held in a Currency Cloud account:** the account is `ONBOARDED` on
  provider `CURRENCY_CLOUD` (so its USD sits on the Currency Cloud side), and
  received USD in the window (direct top-up).
- **B — moved out via Corpay:** the account is `ONBOARDED` on `CORPAY` and was
  active in the window; verified at transaction level by an in-window USD inflow
  **and** a Corpay-side outflow (outward payment or USD→other FX).

Funnel each run: `USD top-up recipients → Currency-Cloud-onboarded →
CC + Corpay + active → with in-window USD movement (Full) vs none (Borderline)`.

## How it works

```
src/cubeClient.js   -> analytics (Cube.js) /load : USD top-up recipients in window
src/hubpayClient.js -> per-account provider onboarding + transactions
src/analysis.js     -> the funnel + transaction-level verification
src/notion.js       -> appends one snapshot row per client to a Notion DB
src/index.js        -> entry point (npm run report)
.github/workflows/refresh.yml -> daily cron + manual "Run" button
```

## Setup

### 1. Notion database

Create a database and add these properties (exact names/types matter):

| Property | Type |
|---|---|
| Client | Title |
| Account ID | Text |
| Tier | Select |
| USD Wallet | Number |
| USD In | Number |
| USD In Count | Number |
| Corpay Outflow USD | Number |
| Outflow Count | Number |
| Match Type | Select |
| Window Days | Number |
| Run Date | Date |

Create an internal integration (notion.so/my-integrations), copy its token, and
**share the database with the integration**. The database id is the 32-char id
in its URL.

### 2. GitHub Actions secrets

Add under *Settings → Secrets and variables → Actions*:

| Secret | Purpose |
|---|---|
| `CUBE_API_URL` | Analytics Cube.js REST base, e.g. `https://…/cubejs-api/v1` |
| `CUBE_API_TOKEN` | Cube.js auth token |
| `HUBPAY_API_URL` | Hubpay platform/ops API base |
| `HUBPAY_API_TOKEN` | Hubpay platform bearer token |
| `NOTION_TOKEN` | Notion integration token (`secret_…`) |
| `NOTION_DATABASE_ID` | Target database id |

### 3. Confirm the platform API paths

The customer-detail and transactions paths are assumed and centralised in
`src/config.js` (`HUBPAY_CUSTOMER_DETAIL_PATH`, `HUBPAY_TRANSACTIONS_PATH`).
**Confirm them against the real Hubpay API** and override via env if needed.

## Run

```bash
npm run report          # compute + publish to Notion
npm run report:dry      # compute + log only (no Notion write)
npm run report:sample   # publish the clients from the original analysis (only NOTION_* needed)
WINDOW_DAYS=45 npm run report
```

Use `report:sample` to validate the Notion database layout before wiring the
live `CUBE_*`/`HUBPAY_*` secrets — it needs only `NOTION_TOKEN` and
`NOTION_DATABASE_ID`. Add `DRY_RUN=true` to any command to log without writing.

Schedule: daily 06:00 GST. Manual runs (Actions → *Run workflow*) accept a
`window_days` and `dry_run` input, which is the interactive knob.

## Scope limits (read before trusting the numbers)

These exist because no single data source ties `account + provider + currency +
time` together; they go away only if a per-account, provider-attributed flow
cube is added to the analytics platform.

1. **Inflow path = direct USD top-ups.** Clients who got USD *purely* via an FX
   conversion into USD on Currency Cloud (no USD top-up) are not enumerable —
   the FX cube has no account dimension.
2. **Provider routing is attributed via onboarding status** (a proxy). The
   transaction API does not tag each transaction's executing provider, so for
   accounts onboarded on both providers the exact rail per transaction is not
   independently confirmed.
