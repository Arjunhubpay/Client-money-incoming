// Thin client for the analytics (Cube.js) REST API.
// We only need the /load endpoint. Query payloads mirror exactly the cube
// names, measures and dimensions used in the original analysis.
import { config } from "./config.js";

async function load(query) {
  const res = await fetch(`${config.cube.url}/load`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: config.cube.token,
    },
    body: JSON.stringify({ query }),
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Cube /load failed: ${res.status} ${body}`);
  }
  const json = await res.json();
  return json.data || [];
}

// Accounts that received a USD top-up within the window.
// Returns: [{ accountId, topupCount, topupAmount }]
export async function usdTopUpRecipients([start, end]) {
  const rows = await load({
    measures: ["FctCompletedTopUps.count", "FctCompletedTopUps.total_amount"],
    dimensions: ["FctCompletedTopUps.user_account_id"],
    filters: [
      {
        member: "FctCompletedTopUps.currency",
        operator: "equals",
        values: ["USD"],
      },
    ],
    timeDimensions: [
      {
        dimension: "FctCompletedTopUps.completed_at",
        dateRange: [start, end],
      },
    ],
    limit: 5000,
  });

  return rows.map((r) => ({
    accountId: r["FctCompletedTopUps.user_account_id"],
    topupCount: Number(r["FctCompletedTopUps.count"] || 0),
    topupAmount: Number(r["FctCompletedTopUps.total_amount"] || 0),
  }));
}
