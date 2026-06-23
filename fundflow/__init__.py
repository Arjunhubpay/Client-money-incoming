"""fundflow — source-agnostic fund-flow pattern detector (v2 handover).

Pipeline: data source -> detector (compliance | commercial) -> sink (Notion).
The defining property: patternStrength is scored independently of attribution
confidence, so ambiguous provider/corridor attribution never suppresses a real
pattern.
"""

__all__ = ["scoring", "models", "attribution", "compliance", "commercial"]
