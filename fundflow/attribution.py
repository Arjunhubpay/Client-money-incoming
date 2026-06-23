"""Provider attribution — the axis that v2 keeps SEPARATE from pattern strength.

The brief's core failure mode: the IBAN prefix on AED-to-AED flows is usually
*ambiguous* (several banks share ranges, or the prefix simply wasn't captured
in transaction metadata). v1 folded that uncertainty into the pattern score and
suppressed real patterns. v2 instead reports providers as labelled-but-uncertain
strings ("Zand or NBF") with a ``providerInferenceMethod`` field naming the
technique, and a confidence number that NEVER feeds back into patternStrength.
"""

from __future__ import annotations

from typing import Optional

# Deliberately small, deliberately ambiguous. Real deployments would load this
# from platform reference data. Some prefixes intentionally map to >1 bank to
# model the AED-to-AED ambiguity the brief calls out.
_IBAN_PREFIX_TO_PROVIDERS = {
    "AE07": ["Zand", "NBF"],          # ambiguous range
    "AE21": ["Mashreq", "ENBD"],      # ambiguous range
    "AE45": ["ADCB"],                 # deterministic
    "AE60": ["FAB"],                  # deterministic
}


def infer_provider(iban: Optional[str]) -> dict:
    """Return {label, confidence (0..100), method} for an IBAN.

    confidence is ONLY about attribution certainty, never pattern strength.
    """
    if not iban:
        return {
            "label": "unknown",
            "confidence": 0.0,
            "method": "no_iban_in_metadata",
        }
    prefix = iban.replace(" ", "")[:4].upper()
    providers = _IBAN_PREFIX_TO_PROVIDERS.get(prefix)
    if not providers:
        return {
            "label": "unknown",
            "confidence": 0.0,
            "method": "prefix_not_in_reference_data",
        }
    if len(providers) == 1:
        return {
            "label": providers[0],
            "confidence": 95.0,
            "method": "iban_prefix_deterministic",
        }
    # Ambiguous: report ALL candidates, low confidence, but do not suppress.
    return {
        "label": " or ".join(providers),
        "confidence": 40.0,
        "method": "iban_prefix_ambiguous",
    }


def combine_leg_attribution(inbound: dict, outbound: dict) -> dict:
    """Combine inbound + outbound attribution into one finding-level attribution.

    NOTE: we average the two confidences for *reporting* only. This is the line
    the brief draws — this number is informational and is never multiplied into
    or min'd with patternStrength.
    """
    label = f"in: {inbound['label']} -> out: {outbound['label']}"
    confidence = round((inbound["confidence"] + outbound["confidence"]) / 2.0, 1)
    method = f"in:{inbound['method']}/out:{outbound['method']}"
    return {"label": label, "confidence": confidence, "method": method}
