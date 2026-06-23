// Notion sink. Each run appends one page per qualifying client (a snapshot),
// tagged with Run Date + Window Days so the database can be filtered/sorted
// interactively (e.g. group by Run Date, filter Match Type = Full).
//
// The target database must have these properties (see README for setup):
//   Client (title), Account ID (text), Tier (select), USD Wallet (number),
//   USD In (number), USD In Count (number), Corpay Outflow USD (number),
//   Outflow Count (number), Match Type (select), Window Days (number),
//   Run Date (date).
import { config } from "./config.js";

const NOTION_API = "https://api.notion.com/v1";

function headers() {
  return {
    Authorization: `Bearer ${config.notion.token}`,
    "Notion-Version": config.notion.version,
    "Content-Type": "application/json",
  };
}

const num = (n) => (Number.isFinite(n) ? Number(n) : 0);

function pageProps(m, runDate, windowDays) {
  return {
    Client: { title: [{ text: { content: m.name || m.accountId } }] },
    "Account ID": { rich_text: [{ text: { content: m.accountId } }] },
    Tier: m.tier ? { select: { name: m.tier } } : { select: null },
    "USD Wallet": { number: num(m.usdWallet) },
    "USD In": { number: num(m.usdInAmount) },
    "USD In Count": { number: num(m.usdInCount) },
    "Corpay Outflow USD": { number: num(m.outflowUsd) },
    "Outflow Count": { number: num(m.outflowCount) },
    "Match Type": { select: { name: m.matchType } },
    "Window Days": { number: num(windowDays) },
    "Run Date": { date: { start: runDate } },
  };
}

export async function publish(matches, { runDate, windowDays }) {
  const results = [];
  for (const m of matches) {
    const res = await fetch(`${NOTION_API}/pages`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({
        parent: { database_id: config.notion.databaseId },
        properties: pageProps(m, runDate, windowDays),
      }),
    });
    if (!res.ok) {
      const body = await res.text().catch(() => "");
      throw new Error(`Notion create page failed for ${m.accountId}: ${res.status} ${body}`);
    }
    results.push(await res.json());
  }
  return results;
}
