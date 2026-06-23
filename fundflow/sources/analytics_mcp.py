"""Option A data source: the Hubpay analytics layer via the platform MCP.

GOVERNANCE BOUNDARY
-------------------
This adapter is deliberately limited to the analytics layer (the
``query-analytics`` MCP tool). It reads AGGREGATED, NON-REGULATED data only:
account name + currency corridor + order count + send amount + order date.

It does NOT read beneficiary names, IBANs, or any per-transaction personal
data. That is the line section 6 of the brief draws between Option A
(commercial intelligence, non-regulated) and Option B (transaction monitoring,
regulated — gated behind MLRO sign-off). Do not extend this adapter to pull
regulated fields without that sign-off.

HOW THE DATA GETS HERE
----------------------
The repo itself does not embed an MCP client. In the "MCP + Claude + Notion"
path, *Claude* is the runtime: Claude calls the ``query-analytics`` MCP tool,
hands the raw JSON rows to ``normalize()`` below, runs ``commercial.detect()``,
and writes the findings to Notion via the sink. ``run.py`` can also replay a
saved JSON pull for offline/testing use.

The query Claude issues (cube: TreasurySettlementDetail):
    measures:   ["TreasurySettlementDetail.count",
                 "TreasurySettlementDetail.total_send_amount"]
    dimensions: ["TreasurySettlementDetail.account_name",
                 "TreasurySettlementDetail.account_type",
                 "TreasurySettlementDetail.send_currency",
                 "TreasurySettlementDetail.receive_currency"]
    timeDimensions: [{dimension: "TreasurySettlementDetail.ordered_at",
                      granularity: "day", dateRange: "last 90 days"}]
"""

from __future__ import annotations

from datetime import datetime
from typing import List

from ..models import FxFlow

# Column keys as returned by the query-analytics MCP tool.
_ACCOUNT = "TreasurySettlementDetail.account_name"
_TYPE = "TreasurySettlementDetail.account_type"
_SEND_CCY = "TreasurySettlementDetail.send_currency"
_RECV_CCY = "TreasurySettlementDetail.receive_currency"
_DAY = "TreasurySettlementDetail.ordered_at.day"
_COUNT = "TreasurySettlementDetail.count"
_SEND_AMT = "TreasurySettlementDetail.total_send_amount"


def normalize(rows: List[dict]) -> List[FxFlow]:
    """Convert raw query-analytics ``data`` rows into FxFlow records."""
    flows: List[FxFlow] = []
    for r in rows:
        day = r[_DAY][:10]  # "2026-06-19T00:00:00.000" -> "2026-06-19"
        flows.append(
            FxFlow(
                account_name=(r.get(_ACCOUNT) or "").strip() or "UNKNOWN",
                account_type=r.get(_TYPE) or "UNKNOWN",
                send_currency=r.get(_SEND_CCY) or "?",
                receive_currency=r.get(_RECV_CCY) or "?",
                ordered_on=datetime.strptime(day, "%Y-%m-%d").date(),
                order_count=int(r.get(_COUNT) or 0),
                send_amount=float(r.get(_SEND_AMT) or 0.0),
            )
        )
    return flows


def load_from_pull(pull: dict) -> List[FxFlow]:
    """Normalize a full query-analytics response object (the ``data`` array)."""
    return normalize(pull.get("data", []))
