"""Orchestrator / CLI for the fund-flow detector.

Usage:
    python -m fundflow.run synthetic
        Run the four validation clients through the compliance detector and
        print findings as JSON (no network).

    python -m fundflow.run commercial --pull path/to/analytics_pull.json
        Normalize a saved query-analytics response (Option A), run the
        commercial detector, and emit Notion-ready page payloads as JSON.

In live operation Claude performs the I/O: it calls the query-analytics MCP
tool, feeds the response to this module's functions, then calls
notion-create-pages with the payloads. This CLI mirrors that flow for offline
runs and tests.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import commercial, compliance
from .sinks import notion as notion_sink
from .sources import analytics_mcp, synthetic


def run_synthetic() -> list:
    findings = compliance.detect(synthetic.load())
    return [f.to_dict() for f in findings]


def run_commercial(pull_path: str) -> dict:
    with open(pull_path) as fh:
        pull = json.load(fh)
    flows = analytics_mcp.load_from_pull(pull)
    findings = commercial.detect(flows)
    return {
        "findings": [f.to_dict() for f in findings],
        "notion_pages": notion_sink.build_pages(findings),
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="fundflow.run")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("synthetic")
    c = sub.add_parser("commercial")
    c.add_argument("--pull", required=True, help="saved query-analytics JSON")
    args = p.parse_args(argv)

    if args.cmd == "synthetic":
        print(json.dumps(run_synthetic(), indent=2))
    elif args.cmd == "commercial":
        print(json.dumps(run_commercial(args.pull), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
