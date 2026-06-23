"""The four synthetic validation clients from section 3 of the brief.

These exercise the four behaviours the detector must get right. They are pure
fixtures — no real data, no database, no network. This is what guarantees the
detector is correct independent of however thin the live data happens to be.

    Meridian  AED layering, tight in->out cycles      -> FIRE  (~strength 87)
    Cobalt    crypto in -> USD out, FX involved        -> FIRE  (~strength 88, fxInvolved)
    Anchor    parks funds: inbounds only, no outbounds -> SILENT
    Harbour   payroll: small in, large unrelated out   -> SILENT  (the key
              false-positive case; +/-5% amount tolerance must suppress it)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

from ..models import Transaction

_BASE = datetime(2026, 4, 1)


def _meridian() -> List[Transaction]:
    """7 tight AED->AED layering cycles: in, then out next day, ~equal amounts."""
    txns: List[Transaction] = []
    amounts = [100_000, 101_500, 99_000, 100_800, 98_700, 101_200, 100_300]
    for i, amt in enumerate(amounts):
        day = _BASE + timedelta(days=i * 5)  # metronomic 5-day cadence
        txns.append(Transaction("meridian", "Meridian Holdings", "IN", amt, "AED",
                                 day, counterparty_iban="AE07 1234 5678 9012 3456"))
        txns.append(Transaction("meridian", "Meridian Holdings", "OUT", amt * 0.995,
                                 "AED", day + timedelta(days=1),
                                 counterparty_iban="AE21 9999 8888 7777 6666"))
    return txns


def _cobalt() -> List[Transaction]:
    """7 cycles crypto(USDT) in -> USD out within window. Cross-currency = FX."""
    txns: List[Transaction] = []
    amounts = [50_000, 50_500, 49_500, 50_200, 49_800, 50_300, 50_100]
    for i, amt in enumerate(amounts):
        day = _BASE + timedelta(days=i * 6)
        txns.append(Transaction("cobalt", "Cobalt Digital", "IN", amt, "USDT", day,
                                 counterparty_iban=None,
                                 meta={"rail": "crypto"}))
        txns.append(Transaction("cobalt", "Cobalt Digital", "OUT", amt * 0.97, "USD",
                                 day + timedelta(days=2), counterparty_iban=None))
    return txns


def _anchor() -> List[Transaction]:
    """Parks funds: 4 inbounds, never moves them out. Must stay SILENT."""
    txns: List[Transaction] = []
    for i, amt in enumerate([250_000, 180_000, 320_000, 210_000]):
        txns.append(Transaction("anchor", "Anchor Estates", "IN", amt, "AED",
                                 _BASE + timedelta(days=i * 9),
                                 counterparty_iban="AE45 1111 2222 3333 4444"))
    return txns


def _harbour() -> List[Transaction]:
    """Payroll: many small salary inbounds + large unrelated supplier outbounds.

    Same currency, but amounts never match within +/-5%, so pairing must find
    zero cycles. This is the classic false positive the tolerance suppresses.
    """
    txns: List[Transaction] = []
    for i in range(8):  # small salary credits
        txns.append(Transaction("harbour", "Harbour Logistics", "IN",
                                 5_000 + i * 50, "AED",
                                 _BASE + timedelta(days=i * 3),
                                 counterparty_iban="AE60 5555 4444 3333 2222"))
    for i in range(3):  # large unrelated supplier payments
        txns.append(Transaction("harbour", "Harbour Logistics", "OUT",
                                 200_000 + i * 1000, "AED",
                                 _BASE + timedelta(days=i * 10 + 2),
                                 counterparty_iban="AE60 5555 4444 3333 2222"))
    return txns


def load() -> List[Transaction]:
    return _meridian() + _cobalt() + _anchor() + _harbour()
