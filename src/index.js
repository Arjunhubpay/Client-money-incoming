// Entry point. Computes the qualifying client list for the trailing window and
// publishes a snapshot to Notion (unless DRY_RUN=true).
import { config, windowRange } from "./config.js";
import { buildReport } from "./analysis.js";
import { publish } from "./notion.js";
import { sampleMatches, sampleStats } from "./sample.js";

function logTable(matches) {
  if (!matches.length) {
    console.log("  (no qualifying clients)");
    return;
  }
  for (const m of matches) {
    console.log(
      `  [${m.matchType}] ${m.name} (${m.accountId}) | tier=${m.tier} | ` +
        `USD wallet=${m.usdWallet} | USD-in=${m.usdInAmount} (${m.usdInCount}) | ` +
        `Corpay-out USD=${m.outflowUsd} (${m.outflowCount} txns)`,
    );
  }
}

async function main() {
  const range = windowRange();
  const runDate = new Date().toISOString().slice(0, 10);
  console.log(
    `Client-money report | window=${config.windowDays}d [${range[0]} -> ${range[1]}] | dryRun=${config.dryRun}`,
  );

  const { matches, nearMisses, stats } = config.sample
    ? { matches: sampleMatches, nearMisses: [], stats: sampleStats }
    : await buildReport(range);

  if (config.sample) console.log("SAMPLE mode: using fixed clients from the original analysis.");

  console.log(
    `Funnel: ${stats.candidates} USD top-up recipients -> ` +
      `${stats.ccOnboarded} Currency-Cloud-onboarded -> ` +
      `${stats.matches} CC+Corpay+active (${stats.fullMatches} with in-window USD movement)`,
  );
  console.log("Matches:");
  logTable(matches);

  if (config.dryRun) {
    console.log(`\nDRY_RUN: skipping Notion write. Near-misses: ${nearMisses.length}`);
    return;
  }

  const pages = await publish(matches, { runDate, windowDays: config.windowDays });
  console.log(`Published ${pages.length} rows to Notion database ${config.notion.databaseId}.`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
