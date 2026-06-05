from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if SRC.exists() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quickbase_structure_client import Auth, QuickBaseStructureClient  # noqa: E402
from quickbase_structure_client.exceptions import QuickbaseError  # noqa: E402

BackupMethod = Literal["schema", "clone"]


class DemoConfigurationError(ValueError):
    """Raised when required demo configuration is missing or invalid."""


@dataclass(frozen=True)
class DemoConfig:
    realm_hostname: str
    user_token: str
    app_name: str
    execute: bool
    auto_backup: bool
    backup_method: BackupMethod
    backup_solution_id: str | None
    backup_dir: Path
    backup_fallback_to_clone: bool
    export_dir: Path
    create_relationship: bool
    trustee_email: str | None
    trustee_role_id: int | None


@dataclass(frozen=True)
class DemoResult:
    app_id: str | None
    users_table_id: str | None
    events_table_id: str | None
    schema_json_path: Path | None
    schema_markdown_path: Path | None


def load_env_file(path: Path) -> dict[str, str]:
    """Load simple KEY=VALUE pairs from .env without requiring python-dotenv."""
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def _env_value(env_file_values: dict[str, str], key: str, default: str = "") -> str:
    return os.environ.get(key, env_file_values.get(key, default)).strip()


def parse_bool(value: str | bool | None, *, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise DemoConfigurationError(f"Expected a boolean value, got {value!r}.")


def parse_optional_int(value: str) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise DemoConfigurationError(f"Expected an integer role id, got {value!r}.") from exc


def build_config(env_file: Path, *, execute_override: bool = False) -> DemoConfig:
    env_file_values = load_env_file(env_file)
    execute = execute_override or parse_bool(
        _env_value(env_file_values, "QUICKBASE_DEMO_EXECUTE"),
        default=False,
    )

    realm_hostname = _env_value(env_file_values, "QUICKBASE_REALM_HOSTNAME")
    user_token = _env_value(env_file_values, "QUICKBASE_USER_TOKEN")
    placeholder_tokens = {"<qb-user-token>", "replace-with-qb-user-token"}
    has_placeholder_realm = realm_hostname in {"", "example.quickbase.com"}
    has_placeholder_token = user_token in {"", *placeholder_tokens}
    if execute and (has_placeholder_realm or has_placeholder_token):
        raise DemoConfigurationError(
            "Real QUICKBASE_REALM_HOSTNAME and QUICKBASE_USER_TOKEN values are required."
        )

    backup_method = _env_value(env_file_values, "QUICKBASE_DEMO_BACKUP_METHOD", "schema")
    if backup_method not in {"schema", "clone"}:
        raise DemoConfigurationError(
            "QUICKBASE_DEMO_BACKUP_METHOD must be either 'schema' or 'clone'."
        )

    return DemoConfig(
        realm_hostname=realm_hostname or "example.quickbase.com",
        user_token=user_token or "<qb-user-token>",
        app_name=_env_value(
            env_file_values,
            "QUICKBASE_DEMO_APP_NAME",
            "PTO Tracking Demo",
        ),
        execute=execute,
        auto_backup=parse_bool(
            _env_value(env_file_values, "QUICKBASE_DEMO_AUTO_BACKUP"),
            default=False,
        ),
        backup_method=backup_method,
        backup_solution_id=_env_value(env_file_values, "QUICKBASE_DEMO_BACKUP_SOLUTION_ID")
        or None,
        backup_dir=Path(_env_value(env_file_values, "QUICKBASE_DEMO_BACKUP_DIR", "demo_backups")),
        backup_fallback_to_clone=parse_bool(
            _env_value(env_file_values, "QUICKBASE_DEMO_BACKUP_FALLBACK_TO_CLONE"),
            default=True,
        ),
        export_dir=Path(_env_value(env_file_values, "QUICKBASE_DEMO_EXPORT_DIR", "demo_exports")),
        create_relationship=parse_bool(
            _env_value(env_file_values, "QUICKBASE_DEMO_CREATE_RELATIONSHIP"),
            default=True,
        ),
        trustee_email=_env_value(env_file_values, "QUICKBASE_DEMO_TRUSTEE_EMAIL") or None,
        trustee_role_id=parse_optional_int(
            _env_value(env_file_values, "QUICKBASE_DEMO_TRUSTEE_ROLE_ID")
        ),
    )


def demo_plan(config: DemoConfig) -> list[str]:
    plan = [
        f"Create app: {config.app_name}",
        "Create Users table with employee name, email, manager, department, PTO balance fields",
        "Create PTO Events table with start/end date, type, status, hours, notes, formula fields",
    ]
    if config.create_relationship:
        plan.append("Create relationship: Users -> PTO Events")
    if config.trustee_email and config.trustee_role_id:
        plan.append(
            f"Add trustee {config.trustee_email} with role id {config.trustee_role_id}"
        )
    plan.append(f"Export schema JSON and Markdown to {config.export_dir}")
    return plan


def print_plan(config: DemoConfig) -> None:
    mode = "EXECUTE" if config.execute else "DRY RUN"
    print(f"PTO tracking demo mode: {mode}")
    print(f"Realm: {config.realm_hostname}")
    print(f"App name: {config.app_name}")
    print(f"Auto backup: {config.auto_backup} ({config.backup_method})")
    print("")
    for index, step in enumerate(demo_plan(config), start=1):
        print(f"{index}. {step}")
    print("")


def _require_created_id(response: dict[str, Any], label: str) -> str:
    created_id = response.get("id")
    if not created_id:
        raise DemoConfigurationError(f"Quickbase did not return an id for {label}: {response!r}")
    return str(created_id)


def _create_fields(
    table: Any,
    definitions: Iterable[tuple[str, str, dict[str, Any]]],
) -> dict[str, Any]:
    created: dict[str, Any] = {}
    for label, field_type, properties in definitions:
        print(f"Creating field: {table.name}.{label}")
        created[label] = table.create_field(label, field_type, properties)
    return created


def run_demo(config: DemoConfig) -> DemoResult:
    auth = Auth(
        config.realm_hostname,
        config.user_token,
        user_agent={"Suffix": "PTO-Demo"},
    )
    client = QuickBaseStructureClient(
        auth,
        auto_backup=config.auto_backup,
        backup_method=config.backup_method,
        backup_solution_id=config.backup_solution_id,
        backup_dir=str(config.backup_dir),
        backup_fallback_to_clone=config.backup_fallback_to_clone,
    )

    print(f"Creating app: {config.app_name}")
    app = client.create_app(
        config.app_name,
        description="Demo PTO tracker created by quickbase-structure-client.",
    )
    if not app.id:
        raise DemoConfigurationError("Quickbase did not return an app id.")

    print("Creating Users table")
    users = app.create_table(
        "User",
        plural_name="Users",
        single_record_name="User",
        description="Employees eligible for PTO.",
    )
    users_table_id = _require_created_id({"id": users.id}, "Users table")

    print("Creating PTO Events table")
    events = app.create_table(
        "PTO Event",
        plural_name="PTO Events",
        single_record_name="PTO Event",
        description="Requested and approved PTO events.",
    )
    events_table_id = _require_created_id({"id": events.id}, "PTO Events table")

    user_fields = _create_fields(
        users,
        [
            ("Employee Name", "text", {"description": "Display name for the employee."}),
            ("Email", "email", {"description": "Employee email address."}),
            ("Manager", "user", {"description": "Employee manager."}),
            ("Department", "text", {"description": "Department or team."}),
            (
                "PTO Balance Hours",
                "numeric",
                {"description": "Current available PTO balance in hours."},
            ),
        ],
    )
    event_fields = _create_fields(
        events,
        [
            ("Start Date", "date", {"description": "First day out."}),
            ("End Date", "date", {"description": "Last day out."}),
            ("PTO Type", "text", {"description": "Vacation, sick, personal, or other."}),
            ("Status", "text", {"description": "Requested, approved, denied, or cancelled."}),
            ("Hours Requested", "numeric", {"description": "Requested PTO hours."}),
            ("Notes", "text", {"description": "Requester or approver notes."}),
            (
                "Requested Days",
                "formula-numeric",
                {
                    "description": "Calendar-day span for the PTO request.",
                    "properties": {"formula": "ToDays([End Date] - [Start Date]) + 1"},
                },
            ),
        ],
    )

    if config.create_relationship:
        employee_name_id = user_fields.get("Employee Name", {}).get("id")
        email_id = user_fields.get("Email", {}).get("id")
        lookup_ids = [field_id for field_id in [employee_name_id, email_id] if field_id]
        try:
            print("Creating relationship: Users -> PTO Events")
            events.create_relationship(
                {
                    "parentTableId": users_table_id,
                    "foreignKeyField": {"label": "Employee"},
                    "lookupFieldIds": lookup_ids,
                    "summaryFields": [],
                }
            )
        except QuickbaseError as exc:
            print(f"Relationship creation failed; continuing with schema export. {exc}")

    if config.trustee_email and config.trustee_role_id:
        print(f"Adding trustee: {config.trustee_email}")
        app.add_trustees(
            [
                {
                    "id": config.trustee_email,
                    "type": "user",
                    "roleId": config.trustee_role_id,
                }
            ]
        )
    elif config.trustee_email or config.trustee_role_id:
        print(
            "Skipping trustee add; QUICKBASE_DEMO_TRUSTEE_EMAIL and "
            "QUICKBASE_DEMO_TRUSTEE_ROLE_ID are both required."
        )

    config.export_dir.mkdir(parents=True, exist_ok=True)
    schema_json_path = config.export_dir / "pto_tracking_schema.json"
    schema_markdown_path = config.export_dir / "pto_tracking_schema.md"
    print(f"Exporting schema to {config.export_dir}")
    schema = client.exporter.compile_schema(app.id)
    client.exporter.to_json(schema, schema_json_path)
    client.exporter.to_markdown(schema, schema_markdown_path)

    print("Demo complete.")
    print(f"App id: {app.id}")
    print(f"Users table id: {users_table_id}")
    print(f"PTO Events table id: {events_table_id}")
    print(f"Schema JSON: {schema_json_path}")
    print(f"Schema Markdown: {schema_markdown_path}")

    return DemoResult(
        app_id=app.id,
        users_table_id=users_table_id,
        events_table_id=events_table_id,
        schema_json_path=schema_json_path,
        schema_markdown_path=schema_markdown_path,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a demo PTO tracking app in Quickbase.",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to the .env file to read. Existing OS environment variables win.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Perform live Quickbase API calls. Without this, the script only prints a plan.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        config = build_config(Path(args.env_file), execute_override=args.execute)
        print_plan(config)
        if not config.execute:
            print("Dry run only. Pass --execute or set QUICKBASE_DEMO_EXECUTE=true to create it.")
            return 0

        run_demo(config)
        return 0
    except (DemoConfigurationError, QuickbaseError) as exc:
        print(f"Demo failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
