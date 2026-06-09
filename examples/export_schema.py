"""Export a Quickbase application or table schema to JSON and Markdown."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if SRC.exists() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quickbase_structure_client import Auth, QuickBaseStructureClient  # noqa: E402
from quickbase_structure_client.exceptions import QuickbaseError  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        description="Export a Quickbase application or table schema as JSON and Markdown."
    )
    parser.add_argument(
        "--app-id",
        required=True,
        help="Quickbase application ID to export.",
    )
    parser.add_argument(
        "--table-id",
        help="Optional Quickbase table ID to export by itself.",
    )
    parser.add_argument(
        "--realm-hostname",
        default=os.environ.get("QUICKBASE_REALM_HOSTNAME"),
        help="Quickbase realm hostname (defaults to QUICKBASE_REALM_HOSTNAME).",
    )
    parser.add_argument(
        "--user-token",
        default=os.environ.get("QUICKBASE_USER_TOKEN"),
        help="Quickbase user token (defaults to QUICKBASE_USER_TOKEN).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("schema_exports"),
        help="Destination directory (default: schema_exports).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Compile and export the requested application schema."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.realm_hostname:
        parser.error(
            "--realm-hostname or the QUICKBASE_REALM_HOSTNAME environment variable is required."
        )
    if not args.user_token:
        parser.error("--user-token or the QUICKBASE_USER_TOKEN environment variable is required.")

    client = QuickBaseStructureClient(
        Auth(args.realm_hostname, args.user_token),
        auto_backup=False,
    )

    try:
        schema = client.exporter.compile_schema(args.app_id, table_id=args.table_id)
        output_name = (
            f"{args.app_id}_{args.table_id}_schema" if args.table_id else f"{args.app_id}_schema"
        )
        json_path = args.output_dir / f"{output_name}.json"
        markdown_path = args.output_dir / f"{output_name}.md"
        client.exporter.to_json(schema, json_path)
        client.exporter.to_markdown(schema, markdown_path)
    except (QuickbaseError, OSError, TypeError, KeyError) as exc:
        print(f"Schema export failed: {exc}", file=sys.stderr)
        return 1

    print(f"JSON schema: {json_path.resolve()}")
    print(f"Markdown schema: {markdown_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
