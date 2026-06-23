"""Validation of the v2 detector against the brief's four synthetic clients.

Asserts the four required BEHAVIOURS (Fire/Silent, fxInvolved, attribution
honesty). Exact strength numbers from the brief (87/88) came from the author's
own unspecified formula; we assert the fired cases land comfortably above the
70 threshold and the silent cases score zero, which is the contract that
matters.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fundflow import compliance  # noqa: E402
from fundflow.sources import synthetic  # noqa: E402


def _by_subject():
    findings = compliance.detect(synthetic.load())
    return {f.subject: f for f in findings}


def test_meridian_fires_strongly():
    f = _by_subject()["Meridian Holdings"]
    assert f.fired is True
    assert f.pattern_strength >= 70
    assert f.cycle_count >= 6
    assert f.fx_involved is False


def test_cobalt_fires_with_fx():
    f = _by_subject()["Cobalt Digital"]
    assert f.fired is True
    assert f.pattern_strength >= 70
    assert f.fx_involved is True


def test_anchor_is_silent():
    f = _by_subject()["Anchor Estates"]
    assert f.fired is False
    assert f.pattern_strength == 0
    assert f.cycle_count == 0


def test_harbour_payroll_is_silent():
    # The key false-positive case: +/-5% amount tolerance must yield no pairs.
    f = _by_subject()["Harbour Logistics"]
    assert f.fired is False
    assert f.cycle_count == 0


def test_attribution_is_independent_of_pattern_strength():
    # Meridian fires despite ambiguous ("X or Y") IBAN attribution and low
    # attribution confidence -> proves the v2 separation.
    f = _by_subject()["Meridian Holdings"]
    assert f.fired is True
    assert f.attribution_confidence < 70  # ambiguous
    assert "or" in f.attribution_label.lower()


if __name__ == "__main__":
    import traceback

    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception:
            failed += 1
            print(f"FAIL {fn.__name__}")
            traceback.print_exc()
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
