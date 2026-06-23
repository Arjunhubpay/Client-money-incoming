"""Notion sink: turn Findings into Notion review-queue pages.

As with the analytics source, the repo holds no Notion SDK client. In the
"MCP + Claude + Notion" path Claude calls the ``notion-create-pages`` MCP tool,
passing the payloads this module builds. Keeping payload construction here (a)
makes it unit-testable without network and (b) pins the database schema in one
place.

Target database schema (created once via notion-create-database):
    Subject        TITLE
    Profile        SELECT(compliance, commercial)
    Status         SELECT(Fire, Silent)
    Pattern Score  NUMBER
    Attribution    RICH_TEXT
    Attr. Conf.    NUMBER
    Attr. Method   RICH_TEXT
    FX Involved    CHECKBOX
    Cycles         NUMBER
    Review Status  SELECT(New, Reviewed, Dismissed, Escalated)
    Summary        RICH_TEXT
"""

from __future__ import annotations

import json
from typing import List

from ..models import Finding


def build_properties(f: Finding) -> dict:
    return {
        "Subject": f.subject,
        "Profile": f.profile,
        "Status": "Fire" if f.fired else "Silent",
        "Pattern Score": f.pattern_strength,
        "Attribution": f.attribution_label,
        "Attr. Conf.": f.attribution_confidence,
        "Attr. Method": f.attribution_method,
        "FX Involved": "__YES__" if f.fx_involved else "__NO__",
        "Cycles": f.cycle_count,
        "Review Status": "New",
        "Summary": f.summary,
    }


def build_content(f: Finding) -> str:
    """Notion-flavored markdown body with the scoring breakdown and evidence."""
    c = f.components
    lines = [
        f"**{f.summary}**",
        "",
        "## Pattern score breakdown",
        f"- Recurrence: `{c.get('recurrence')}`",
        f"- Amount consistency (1 - CV): `{c.get('amountConsistency')}`",
        f"- Interval regularity (1 - CV): `{c.get('intervalRegularity')}`",
        f"- **patternStrength: `{f.pattern_strength}`** "
        f"({'FIRE' if f.fired else 'silent'})",
        "",
        "## Attribution (independent axis — never lowers pattern score)",
        f"- Label: {f.attribution_label}",
        f"- Confidence: `{f.attribution_confidence}`",
        f"- Method: `{f.attribution_method}`",
        f"- FX involved: {'yes' if f.fx_involved else 'no'}",
        "",
        "## Evidence",
        "```json",
        json.dumps(f.evidence, indent=2),
        "```",
    ]
    return "\n".join(lines)


def build_pages(findings: List[Finding]) -> List[dict]:
    """Build the ``pages`` array for the notion-create-pages MCP tool."""
    pages = []
    for f in findings:
        pages.append({
            "properties": build_properties(f),
            "content": build_content(f),
            "icon": "🔥" if f.fired else "🟢",
        })
    return pages


# DDL used once to create the database (see README / notion-create-database).
CREATE_TABLE_DDL = (
    'CREATE TABLE ('
    '"Subject" TITLE, '
    '"Profile" SELECT(\'compliance\':blue, \'commercial\':green), '
    '"Status" SELECT(\'Fire\':red, \'Silent\':gray), '
    '"Pattern Score" NUMBER, '
    '"Attribution" RICH_TEXT, '
    '"Attr. Conf." NUMBER, '
    '"Attr. Method" RICH_TEXT, '
    '"FX Involved" CHECKBOX, '
    '"Cycles" NUMBER, '
    '"Review Status" SELECT(\'New\':yellow, \'Reviewed\':blue, '
    '\'Dismissed\':gray, \'Escalated\':red), '
    '"Summary" RICH_TEXT)'
)
