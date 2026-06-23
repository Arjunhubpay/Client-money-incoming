"""Compliance profile: per-client inbound<->outbound conduit/layering detector.

This is the original brief use case. It pairs inbound and outbound transactions
within +/-7 days and (for same-currency pairs) +/-5% amount tolerance, scores
the resulting cycles, and FIRES when patternStrength >= 70 regardless of how
confident provider attribution is.

Validated by the four synthetic clients in the brief (see tests/):
    Meridian  AED layering, tight in->out cycles      -> FIRE
    Cobalt    crypto in -> USD out, FX involved        -> FIRE (fxInvolved)
    Anchor    parks funds: inbounds only, no outbounds -> SILENT
    Harbour   payroll: small in, large unrelated out   -> SILENT
"""

from __future__ import annotations

from collections import defaultdict
from typing import List

from .attribution import combine_leg_attribution, infer_provider
from .models import Finding, Transaction
from .scoring import pattern_strength

FIRE_THRESHOLD = 70.0
DAYS_WINDOW = 7
AMOUNT_TOLERANCE = 0.05  # +/-5%


def _pair_cycles(txns: List[Transaction]) -> dict:
    """Pair each inbound with the nearest eligible outbound -> list of cycles.

    Same-currency pairs must match within +/-5% amount. Cross-currency pairs
    are FX-involved: we pair on timing alone and skip amount tolerance (a known
    v2 limitation — no FX normalisation step yet) and flag fxInvolved.
    """
    inbound = sorted([t for t in txns if t.direction == "IN"], key=lambda t: t.timestamp)
    outbound = sorted([t for t in txns if t.direction == "OUT"], key=lambda t: t.timestamp)

    used_out = set()
    cycles = []
    fx_involved = False

    for tin in inbound:
        best = None
        for i, tout in enumerate(outbound):
            if i in used_out:
                continue
            if tout.timestamp < tin.timestamp:
                continue
            gap_days = (tout.timestamp - tin.timestamp).days
            if gap_days > DAYS_WINDOW:
                continue
            same_ccy = tin.currency == tout.currency
            if same_ccy:
                rel = abs(tout.amount - tin.amount) / tin.amount if tin.amount else 1.0
                if rel > AMOUNT_TOLERANCE:
                    continue
            # else: cross-currency, FX involved, amount tolerance not applied
            if best is None or tout.timestamp < outbound[best].timestamp:
                best = i
        if best is not None:
            used_out.add(best)
            tout = outbound[best]
            if tin.currency != tout.currency:
                fx_involved = True
            cycles.append((tin, tout))

    return {"cycles": cycles, "fx_involved": fx_involved}


def detect(transactions: List[Transaction]) -> List[Finding]:
    by_client: dict[str, List[Transaction]] = defaultdict(list)
    for t in transactions:
        by_client[t.client_id].append(t)

    findings: List[Finding] = []
    for client_id, txns in by_client.items():
        name = txns[0].client_name
        paired = _pair_cycles(txns)
        cycles = paired["cycles"]

        inbound_amounts = [tin.amount for tin, _ in cycles]
        day0 = min((t.timestamp for t in txns))
        in_days = [(tin.timestamp - day0).days for tin, _ in cycles]

        score = pattern_strength(
            cycle_count=len(cycles),
            amounts=inbound_amounts,
            timestamps_days=in_days,
        )

        # Attribution — computed independently, never feeds patternStrength.
        if cycles:
            attr = combine_leg_attribution(
                infer_provider(cycles[0][0].counterparty_iban),
                infer_provider(cycles[0][1].counterparty_iban),
            )
        else:
            attr = {"label": "n/a", "confidence": 0.0, "method": "no_cycles"}

        fired = score["patternStrength"] >= FIRE_THRESHOLD
        summary = (
            f"{len(cycles)} paired in->out cycle(s); "
            f"patternStrength {score['patternStrength']} "
            f"({'FIRE' if fired else 'silent'})"
            + (" | FX involved" if paired["fx_involved"] else "")
        )

        findings.append(
            Finding(
                subject=name,
                profile="compliance",
                fired=fired,
                pattern_strength=score["patternStrength"],
                attribution_confidence=attr["confidence"],
                attribution_label=attr["label"],
                attribution_method=attr["method"],
                fx_involved=paired["fx_involved"],
                cycle_count=len(cycles),
                components=score["components"],
                summary=summary,
                evidence={
                    "inboundCount": sum(1 for t in txns if t.direction == "IN"),
                    "outboundCount": sum(1 for t in txns if t.direction == "OUT"),
                    "pairedCycles": len(cycles),
                },
            )
        )
    return findings
