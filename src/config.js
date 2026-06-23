// Central configuration. Everything is driven by environment variables so the
// same code runs locally (`npm run report`) and in GitHub Actions (cron).
//
// Required secrets (set as GitHub Actions repository secrets):
//   CUBE_API_URL      - base URL of the analytics (Cube.js) REST API, e.g. https://analytics.hubpay.../cubejs-api/v1
//   CUBE_API_TOKEN    - bearer/auth token for the Cube.js API
//   HUBPAY_API_URL    - base URL of the Hubpay platform/ops API
//   HUBPAY_API_TOKEN  - bearer token for the Hubpay platform API
//   NOTION_TOKEN      - Notion internal integration token (secret_...)
//   NOTION_DATABASE_ID- target Notion database id (the integration must be shared on it)
//
// Optional (have sensible defaults):
//   WINDOW_DAYS       - trailing window in days (default 30)
//   DRY_RUN           - "true" => compute + log, do not write to Notion
//   HUBPAY_CUSTOMER_DETAIL_PATH - path template for customer detail, {id} substituted
//   HUBPAY_TRANSACTIONS_PATH    - path template for transactions, {id} substituted

// `neededInSample` = whether the variable is still required when running in
// sample mode (e.g. Notion creds are; the live data APIs are not).
function required(name, neededInSample = true) {
  const v = process.env[name];
  const skip = isDryRun() || (isSample() && !neededInSample);
  if (!v && !skip) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return v ?? "";
}

export function isDryRun() {
  return String(process.env.DRY_RUN || "").toLowerCase() === "true";
}

export function isSample() {
  return String(process.env.SAMPLE || "").toLowerCase() === "true";
}

export const config = {
  windowDays: Number(process.env.WINDOW_DAYS || 30),
  dryRun: isDryRun(),
  sample: isSample(),

  cube: {
    url: required("CUBE_API_URL", false),
    token: process.env.CUBE_API_TOKEN || "",
  },

  hubpay: {
    url: required("HUBPAY_API_URL", false),
    token: process.env.HUBPAY_API_TOKEN || "",
    // NOTE: confirm these paths against the real Hubpay platform API. They are
    // centralised here so only this file changes if the contract differs.
    customerDetailPath:
      process.env.HUBPAY_CUSTOMER_DETAIL_PATH || "/customers/{id}/detail",
    transactionsPath:
      process.env.HUBPAY_TRANSACTIONS_PATH || "/customers/{id}/transactions",
  },

  notion: {
    token: required("NOTION_TOKEN"),
    databaseId: required("NOTION_DATABASE_ID"),
    version: "2022-06-28",
  },
};

// Returns [startISODate, endISODate] (date-only, inclusive) for the trailing window.
export function windowRange(days = config.windowDays, now = new Date()) {
  const end = new Date(now);
  const start = new Date(now);
  start.setUTCDate(start.getUTCDate() - days);
  const fmt = (d) => d.toISOString().slice(0, 10);
  return [fmt(start), fmt(end)];
}
