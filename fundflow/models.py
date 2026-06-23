"""Normalized data models shared across data sources, detector and sinks.

Every data source (synthetic fixtures, analytics MCP, future live MCP) must
normalize into these models so the detector stays completely source-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import Optional


@dataclass
class Transaction:
    """A single client-level money movement (compliance / layering profile)."""

    client_id: str
    client_name: str
    direction: str  # "IN" or "OUT"
    amount: float
    currency: str
    timestamp: datetime
    counterparty_iban: Optional[str] = None
    meta: dict = field(default_factory=dict)


@dataclass
class FxFlow:
    """An aggregated per-account FX order bucket (commercial / Option-A profile).

    Sourced from the analytics layer (TreasurySettlementDetail). Carries NO
    beneficiary / IBAN / personal data — aggregated, non-regulated.
    """

    account_name: str
    account_type: str
    send_currency: str
    receive_currency: str
    ordered_on: date
    order_count: int
    send_amount: float

    @property
    def corridor(self) -> str:
        return f"{self.send_currency}/{self.receive_currency}"


@dataclass
class Finding:
    """A scored result emitted by the detector, destined for Notion."""

    subject: str  # client name or account name
    profile: str  # "compliance" | "commercial"
    fired: bool
    pattern_strength: float
    attribution_confidence: float
    attribution_label: str  # e.g. "Zand or NBF" or "AED/USD corridor"
    attribution_method: str
    fx_involved: bool
    cycle_count: int
    components: dict
    summary: str
    evidence: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)
