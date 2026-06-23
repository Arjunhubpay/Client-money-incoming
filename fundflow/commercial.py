"""Commercial profile (Option A): forward-contract opportunity scoring.

This is the NON-REGULATED reframe from section 6 of the brief: instead of
flagging conduits for compliance, we spot clients with recurring, sizeable,
regular FX flows who would benefit from a forward contract instead of repeated
spot conversions.

It reuses the EXACT same scoring engine as the compliance profile — recurrence,
amount consistency, interval regularity — proving the v2 architecture is
genuinely source- and use-case-agnostic. Here ``attributionConfidence`` reflects
how confident we are that the flow is a stable recurring corridor (a function of
how many cycles we actually observed), kept separate from opportunity strength.

Input: aggregated ``FxFlow`` rows from the analytics layer. No regulated data.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import List

from .models import Finding, FxFlow
from .scoring import pattern_strength

# Opportunity bar: a meaningful, recurring FX flow worth a forward conversation.
OPPORTUNITY_THRESHOLD = 50.0
# Minimum total volume (in send-currency units) to bother surfacing at all.
MIN_TOTAL_VOLUME = 100_000.0


def _attribution_from_cycles(cycle_count: int, corridor: str) -> dict:
    """Confidence that this corridor is a *stable recurring* relationship.

    Separate axis from opportunity strength. A single large order is a strong
    opportunity *signal* but a weak *recurrence attribution* — we report both
    honestly rather than letting one mask the other.
    """
    if cycle_count >= 4:
        conf, method = 90.0, "observed_4plus_cycles"
    elif cycle_count >= 2:
        conf, method = 60.0, "observed_2to3_cycles"
    else:
        conf, method = 20.0, "single_observation"
    return {"label": f"{corridor} corridor", "confidence": conf, "method": method}


def detect(flows: List[FxFlow]) -> List[Finding]:
    # Group by account + corridor: a forward contract is corridor-specific.
    grouped: dict[tuple, List[FxFlow]] = defaultdict(list)
    for f in flows:
        grouped[(f.account_name, f.corridor)].append(f)

    findings: List[Finding] = []
    for (account, corridor), bucket in grouped.items():
        bucket.sort(key=lambda f: f.ordered_on)
        cycle_count = sum(f.order_count for f in bucket)
        amounts = [f.send_amount for f in bucket]
        total_volume = sum(amounts)
        if total_volume < MIN_TOTAL_VOLUME:
            continue

        day0: date = bucket[0].ordered_on
        days = [(f.ordered_on - day0).days for f in bucket]

        score = pattern_strength(
            cycle_count=cycle_count, amounts=amounts, timestamps_days=days
        )
        attr = _attribution_from_cycles(cycle_count, corridor)
        fired = score["patternStrength"] >= OPPORTUNITY_THRESHOLD
        send_ccy = bucket[0].send_currency

        summary = (
            f"{account}: {cycle_count} FX order(s) on {corridor}, "
            f"total {total_volume:,.0f} {send_ccy}; "
            f"opportunityStrength {score['patternStrength']}"
            + (" -> FORWARD CANDIDATE" if fired else " (below bar)")
        )

        findings.append(
            Finding(
                subject=account,
                profile="commercial",
                fired=fired,
                pattern_strength=score["patternStrength"],
                attribution_confidence=attr["confidence"],
                attribution_label=attr["label"],
                attribution_method=attr["method"],
                fx_involved=True,
                cycle_count=cycle_count,
                components=score["components"],
                summary=summary,
                evidence={
                    "corridor": corridor,
                    "totalVolume": round(total_volume, 2),
                    "sendCurrency": send_ccy,
                    "accountType": bucket[0].account_type,
                    "firstOrdered": str(day0),
                    "lastOrdered": str(bucket[-1].ordered_on),
                },
            )
        )

    findings.sort(key=lambda f: f.evidence["totalVolume"], reverse=True)
    return findings
