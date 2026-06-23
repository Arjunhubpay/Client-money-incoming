// Core pipeline: from "USD top-up recipients" to the qualifying client list.
//
// Condition (as defined with the business):
//   A. USD held in a Currency Cloud account  -> account ONBOARDED on CURRENCY_CLOUD
//   B. Moved out via Corpay                   -> account ONBOARDED on CORPAY and active in window
// Verified at transaction level for matches: in-window USD inflow + Corpay-side outflow.
//
// Known scope limits (documented in README):
//   - Inflow path covered = direct USD top-ups (FX-into-USD-on-CC-only clients are
//     not enumerable from analytics, which has no account-level FX-by-provider data).
//   - Provider routing is attributed via onboarding status (proxy), since the
//     transaction API does not tag each transaction's provider.
import { usdTopUpRecipients } from "./cubeClient.js";
import {
  getCustomerDetail,
  getTransactions,
  isOnboarded,
  providerStatus,
} from "./hubpayClient.js";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Process items with limited concurrency to respect API rate limits.
async function mapLimit(items, limit, fn, pauseMs = 1500) {
  const out = [];
  for (let i = 0; i < items.length; i += limit) {
    const slice = items.slice(i, i + limit);
    out.push(...(await Promise.all(slice.map(fn))));
    if (i + limit < items.length) await sleep(pauseMs);
  }
  return out;
}

function usdWallet(detail) {
  const account = detail.account || detail;
  const balances = detail.walletBalances || account.walletBalances || [];
  const usd = balances.find((b) => b.currencyCode === "USD");
  return usd ? Number(usd.amount || 0) : 0;
}

// Summarise in-window inflows/outflows from a transaction list.
function flows(transactions, startISO) {
  const inWindow = transactions.filter((t) => (t.createdAt || "") >= startISO);
  let usdInCount = 0;
  let usdInAmount = 0;
  let outflowCount = 0;
  let outflowUsd = 0;

  for (const t of inWindow) {
    const type = t.type || "";
    const rcv = t.receiverAmount || {};
    const snd = t.senderAmount || {};

    const isUsdIn =
      (/TOP_UP/.test(type) && rcv.currency === "USD") ||
      (type === "FOREIGN_EXCHANGE" && rcv.currency === "USD");
    if (isUsdIn) {
      usdInCount += 1;
      usdInAmount += Number(rcv.amount || 0);
    }

    const isPayment = type === "PAYMENT";
    const isUsdSellFx = type === "FOREIGN_EXCHANGE" && snd.currency === "USD";
    if (isPayment || isUsdSellFx) {
      outflowCount += 1;
      if (isPayment && rcv.currency === "USD") outflowUsd += Number(rcv.amount || 0);
      if (isUsdSellFx) outflowUsd += Number(snd.amount || 0);
    }
  }
  return { usdInCount, usdInAmount, outflowCount, outflowUsd };
}

// Returns { matches, nearMisses, stats }
export async function buildReport(windowRange) {
  const [start] = windowRange;
  const candidates = await usdTopUpRecipients(windowRange);

  const details = await mapLimit(candidates, 5, async (c) => {
    try {
      const detail = await getCustomerDetail(c.accountId);
      return { c, detail };
    } catch (e) {
      return { c, error: String(e.message || e) };
    }
  });

  const ccOnboarded = [];
  for (const d of details) {
    if (d.error || !isOnboarded(d.detail, "CURRENCY_CLOUD")) continue;
    ccOnboarded.push(d);
  }

  const matches = [];
  const nearMisses = [];

  // Gate B + transaction verification, for CC-onboarded accounts.
  const gateB = ccOnboarded.filter((d) => {
    const account = d.detail.account || d.detail;
    const summary = d.detail.last30DaysSummary || account.last30DaysSummary || {};
    const corpay = isOnboarded(d.detail, "CORPAY");
    const active = Number(summary.totalTransactions || 0) > 0;
    if (corpay && active) return true;
    nearMisses.push({
      name: (account.fullName || "").trim(),
      accountId: account.id || d.c.accountId,
      reason: corpay ? "no activity in last 30d" : `CORPAY=${providerStatus(d.detail, "CORPAY")}`,
    });
    return false;
  });

  const verified = await mapLimit(gateB, 4, async (d) => {
    const account = d.detail.account || d.detail;
    const summary = d.detail.last30DaysSummary || account.last30DaysSummary || {};
    let f = { usdInCount: 0, usdInAmount: 0, outflowCount: 0, outflowUsd: 0 };
    try {
      const txns = await getTransactions(d.c.accountId, { size: 100, pages: 2 });
      f = flows(txns, start);
    } catch (e) {
      // keep zeros; transaction read failed
    }
    const fullMovement = f.usdInCount > 0 && f.outflowCount > 0;
    return {
      name: (account.fullName || "").trim(),
      accountId: account.id || d.c.accountId,
      tier: account.businessAccountTier || account.accountTier || "",
      usdWallet: usdWallet(d.detail),
      txns30d: Number(summary.totalTransactions || 0),
      volume30d: Number(summary.totalVolume || 0),
      ...f,
      matchType: fullMovement ? "Full" : "Borderline",
    };
  });

  matches.push(...verified);

  const stats = {
    candidates: candidates.length,
    ccOnboarded: ccOnboarded.length,
    matches: matches.length,
    fullMatches: matches.filter((m) => m.matchType === "Full").length,
  };

  return { matches, nearMisses, stats };
}
