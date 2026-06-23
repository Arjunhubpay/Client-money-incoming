// Client for the Hubpay platform/ops API: per-account provider attribution
// (which the analytics cubes do not expose) plus transaction history.
import { config } from "./config.js";

async function get(pathTemplate, id, query = {}) {
  const path = pathTemplate.replace("{id}", encodeURIComponent(id));
  const url = new URL(`${config.hubpay.url}${path}`);
  for (const [k, v] of Object.entries(query)) url.searchParams.set(k, String(v));

  const res = await fetch(url, {
    headers: {
      Authorization: `Bearer ${config.hubpay.token}`,
      Accept: "application/json",
    },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Hubpay GET ${path} failed: ${res.status} ${body}`);
  }
  return res.json();
}

export function getCustomerDetail(accountId) {
  return get(config.hubpay.customerDetailPath, accountId);
}

// Paged transactions; returns the flat content array (most recent first).
export async function getTransactions(accountId, { size = 100, pages = 2 } = {}) {
  const all = [];
  for (let page = 0; page < pages; page++) {
    const data = await get(config.hubpay.transactionsPath, accountId, { size, page });
    const content = data.content || data.items || data || [];
    all.push(...content);
    const totalPages = data.totalPages ?? 1;
    if (page + 1 >= totalPages) break;
  }
  return all;
}

// Helpers to read provider onboarding status from a customer-detail payload.
export function providerStatus(detail, provider) {
  const account = detail.account || detail;
  const list = account.paymentProviderOnboardings || [];
  const entry = list.find((p) => p.paymentProvider === provider);
  return entry ? entry.onboardingStatus : "NONE";
}

export function isOnboarded(detail, provider) {
  return providerStatus(detail, provider) === "ONBOARDED";
}
