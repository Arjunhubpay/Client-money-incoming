"""Shared scoring primitives for the fund-flow detector.

This module is the architectural heart of the v2 handover brief: it scores
*how strong / regular a flow pattern is* completely separately from *how
confident we are about attribution* (which bank, which corridor).

The old v1 logic conflated the two with ``min(inbound_conf, outbound_conf)``,
which silently suppressed real patterns whenever provider attribution was
ambiguous (i.e. most AED-to-AED flows). v2 never lets attribution uncertainty
lower the pattern score. They are two independent axes:

    patternStrength       -> recurrence + amount consistency + interval regularity
    attributionConfidence -> only how deterministically we can name the
                             provider / corridor from available metadata

Nothing here is specific to compliance vs. commercial use. Both profiles
(``compliance`` layering detection and ``commercial`` forward-contract
opportunity scoring) reuse these primitives.
"""

from __future__ import annotations

from statistics import mean, pstdev
from typing import Sequence


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def coefficient_of_variation(values: Sequence[float]) -> float:
    """CV = stddev / mean. Returns 0.0 for <2 values or a zero mean.

    Lower CV means more consistent. We use population stddev because we are
    describing the observed set of cycles, not sampling from a population.
    """
    if len(values) < 2:
        return 0.0
    m = mean(values)
    if m == 0:
        return 0.0
    return pstdev(values) / abs(m)


def recurrence_score(cycle_count: int, saturate_at: int = 6) -> float:
    """0..1, saturating once a pattern has repeated ``saturate_at`` times.

    Per the brief: scores saturate at high recurrence. Deliberate — we do not
    want a flow with 100 cycles to score 10x a flow with 10; both are clearly
    recurring. Saturation keeps strong patterns comparable.
    """
    if cycle_count <= 1:
        return 0.0
    return clamp(min(cycle_count, saturate_at) / saturate_at)


def amount_consistency_score(amounts: Sequence[float]) -> float:
    """1 - CV of amounts, clamped to [0,1]. High = tightly clustered amounts."""
    if len(amounts) < 2:
        return 0.0
    return clamp(1.0 - coefficient_of_variation(amounts))


def interval_regularity_score(timestamps_days: Sequence[float]) -> float:
    """1 - CV of inter-arrival gaps, clamped. High = metronomic cadence.

    ``timestamps_days`` is an ascending sequence of day-offsets (floats).
    """
    if len(timestamps_days) < 3:
        # need >=3 events to have >=2 intervals to judge regularity
        return 0.0
    ordered = sorted(timestamps_days)
    intervals = [b - a for a, b in zip(ordered, ordered[1:])]
    return clamp(1.0 - coefficient_of_variation(intervals))


# Weights for combining the three pattern axes. Recurrence is weighted highest:
# a one-off is never a pattern, no matter how "consistent" a single number is.
PATTERN_WEIGHTS = {"recurrence": 0.4, "consistency": 0.3, "regularity": 0.3}


def pattern_strength(
    cycle_count: int,
    amounts: Sequence[float],
    timestamps_days: Sequence[float],
    weights: dict | None = None,
) -> dict:
    """Combine the three axes into a 0..100 patternStrength with a breakdown."""
    w = weights or PATTERN_WEIGHTS
    rec = recurrence_score(cycle_count)
    cons = amount_consistency_score(amounts)
    reg = interval_regularity_score(timestamps_days)
    strength = 100.0 * (
        w["recurrence"] * rec + w["consistency"] * cons + w["regularity"] * reg
    )
    return {
        "patternStrength": round(strength, 1),
        "components": {
            "recurrence": round(rec, 3),
            "amountConsistency": round(cons, 3),
            "intervalRegularity": round(reg, 3),
        },
        "cycleCount": cycle_count,
    }
