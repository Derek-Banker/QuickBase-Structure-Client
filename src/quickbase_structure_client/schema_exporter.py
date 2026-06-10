"""Utilities for exporting Quickbase application schemas."""

from __future__ import annotations

import json
import logging
import math
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List

from quickbase_structure_client.exceptions import (
    QuickbaseSchemaError,
    QuickbaseValidationError,
    format_error_message,
)

if TYPE_CHECKING:
    from quickbase_structure_client.quickbase_api import QuickBaseStructureClient
    from quickbase_structure_client.table import StructureTable

logger = logging.getLogger(__name__)

DEFAULT_REQUEST_INTERVAL_SECONDS = 0.11


class SchemaExporter:
    """Export Quickbase application schemas as JSON or Markdown.

    Attributes:
        api_client: Client used to retrieve Quickbase schema information.
    """

    def __init__(self, api_client: QuickBaseStructureClient) -> None:
        """Initialize the schema exporter.

        Args:
            api_client: Client used to execute API requests.
        """
        self.api_client = api_client

    @staticmethod
    def _markdown_cell(value: Any) -> str:
        """Escape a value for use in a Markdown table cell.

        Args:
            value: Value to render.

        Returns:
            A Markdown-safe string.
        """
        if value is None:
            return ""
        return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")

    def _compile_table(
        self,
        app_id: str,
        table_info: Dict[str, Any],
        table_ref: StructureTable,
        wait_for_request_slot: Callable[[], None],
    ) -> Dict[str, Any]:
        """Compile one table's fields and child relationships.

        Args:
            app_id: Parent Quickbase application ID.
            table_info: Table metadata returned by Quickbase.
            table_ref: Bound table reference used for child lookups.
            wait_for_request_slot: Callback that paces Quickbase lookups.

        Returns:
            A dictionary containing the compiled table schema.

        Raises:
            QuickbaseSchemaError: If the table has no ID, or fields or
                relationships cannot be retrieved.
        """
        table_id = table_info.get("id")
        if table_id is None:
            raise QuickbaseSchemaError(
                format_error_message(
                    "Quickbase returned a table without an ID.",
                    operation="SchemaExporter.compile_schema",
                    app_id=app_id,
                    table=table_info,
                )
            )
        table_id = str(table_id)
        table_schema: Dict[str, Any] = {
            "id": table_id,
            "name": table_info.get("name"),
            "plural_name": table_info.get("pluralRecordName") or table_info.get("pluralName"),
            "description": table_info.get("description"),
            "fields": [],
            "relationships": [],
        }

        try:
            wait_for_request_slot()
            for field_info in table_ref.list_fields():
                properties = field_info.get("properties", {})
                table_schema["fields"].append(
                    {
                        "id": field_info.get("id"),
                        "label": field_info.get("label"),
                        "type": field_info.get("fieldType"),
                        "formula": properties.get("formula"),
                        "unique": field_info.get(
                            "unique",
                            properties.get("unique", False),
                        ),
                        "required": field_info.get(
                            "required",
                            properties.get("required", False),
                        ),
                    }
                )
        except Exception as exc:
            raise QuickbaseSchemaError(
                format_error_message(
                    "Failed to fetch fields while compiling the schema.",
                    operation="SchemaExporter.compile_schema",
                    app_id=app_id,
                    table_id=table_id,
                    cause=exc,
                )
            ) from exc

        try:
            wait_for_request_slot()
            for relationship in table_ref.list_relationships():
                table_schema["relationships"].append(
                    {
                        "relationship_id": relationship.get("id"),
                        "parent_table_id": relationship.get("parentTableId"),
                        "parent_table_name": relationship.get("parentTableName"),
                        "reference_field_id": relationship.get("referenceFieldId"),
                        "reference_field_label": relationship.get("referenceFieldLabel"),
                    }
                )
        except Exception as exc:
            raise QuickbaseSchemaError(
                format_error_message(
                    "Failed to fetch relationships while compiling the schema.",
                    operation="SchemaExporter.compile_schema",
                    app_id=app_id,
                    table_id=table_id,
                    cause=exc,
                )
            ) from exc

        return table_schema

    def compile_schema(
        self,
        app_id: str,
        *,
        table_id: str | None = None,
        request_interval: float = DEFAULT_REQUEST_INTERVAL_SECONDS,
    ) -> Dict[str, Any]:
        """Compile an application's structural schema.

        The compiled schema contains application metadata, tables, fields,
        formulas, and relationships for which each table is the child. When
        ``table_id`` is supplied, only that table is compiled. Requests are
        paced by default to avoid exceeding Quickbase's documented general
        API rate limit.

        Args:
            app_id: Quickbase application ID.
            table_id: Optional Quickbase table ID to compile by itself.
            request_interval: Minimum seconds between schema lookup requests.
                Set to ``0`` to disable pacing.

        Returns:
            A dictionary containing the compiled application schema. A
            single-table export retains the same shape with one item in
            ``tables``.

        Raises:
            QuickbaseValidationError: If ``table_id`` is empty or
                ``request_interval`` is invalid.
            QuickbaseSchemaError: If Quickbase returns invalid table metadata,
                or if fields or relationships cannot be retrieved.
            QuickbaseError: If application or table retrieval fails.
        """
        if table_id is not None and not table_id.strip():
            raise QuickbaseValidationError(
                format_error_message(
                    "table_id must be a non-empty string when provided.",
                    operation="SchemaExporter.compile_schema",
                    app_id=app_id,
                )
            )

        if (
            isinstance(request_interval, bool)
            or not isinstance(request_interval, (int, float))
            or not math.isfinite(request_interval)
            or request_interval < 0
        ):
            raise QuickbaseValidationError(
                format_error_message(
                    "request_interval must be a finite, non-negative number.",
                    operation="SchemaExporter.compile_schema",
                    app_id=app_id,
                    request_interval=request_interval,
                )
            )
        request_interval = float(request_interval)

        logger.info(
            "Compiling schema structure for app %s%s",
            app_id,
            f", table {table_id}" if table_id is not None else "",
        )

        last_request_started_at: float | None = None

        def wait_for_request_slot() -> None:
            """Wait until the next schema lookup can start."""
            nonlocal last_request_started_at

            now = time.monotonic()
            if last_request_started_at is not None:
                remaining = request_interval - (now - last_request_started_at)
                if remaining > 0:
                    time.sleep(remaining)
                    now = time.monotonic()
            last_request_started_at = now

        app_ref = self.api_client.app(id=app_id)
        wait_for_request_slot()
        app_details = app_ref.get_details()

        schema: Dict[str, Any] = {
            "app_id": app_id,
            "name": app_details.get("name"),
            "description": app_details.get("description"),
            "tables": [],
        }

        if table_id is not None:
            table_ref = app_ref.table(id=table_id)
            wait_for_request_slot()
            table_info = dict(table_ref.get_details())
            table_info["id"] = table_id
            schema["tables"].append(
                self._compile_table(
                    app_id,
                    table_info,
                    table_ref,
                    wait_for_request_slot,
                )
            )
            return schema

        wait_for_request_slot()
        for table_info in app_ref.list_tables():
            listed_table_id = table_info.get("id")
            if listed_table_id is None:
                raise QuickbaseSchemaError(
                    format_error_message(
                        "Quickbase returned a table without an ID.",
                        operation="SchemaExporter.compile_schema",
                        app_id=app_id,
                        table=table_info,
                    )
                )
            table_ref = app_ref.table(id=str(listed_table_id))
            schema["tables"].append(
                self._compile_table(
                    app_id,
                    table_info,
                    table_ref,
                    wait_for_request_slot,
                )
            )

        return schema

    def to_json(self, schema: Dict[str, Any], filepath: str | Path | None = None) -> str:
        """Serialize a compiled schema as pretty-printed JSON.

        Args:
            schema: Schema produced by :meth:`compile_schema`.
            filepath: Optional destination file path.

        Returns:
            The serialized JSON document.

        Raises:
            TypeError: If the schema contains values that cannot be serialized.
            OSError: If the destination directory or file cannot be written.
        """
        json_str = json.dumps(schema, indent=2, ensure_ascii=False)
        if filepath:
            path = Path(filepath)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json_str, encoding="utf-8")
        return json_str

    def to_markdown(self, schema: Dict[str, Any], filepath: str | Path | None = None) -> str:
        """Format a compiled schema as hierarchical Markdown.

        Args:
            schema: Schema produced by :meth:`compile_schema`.
            filepath: Optional destination file path.

        Returns:
            The generated Markdown document.

        Raises:
            KeyError: If required schema collections are missing.
            OSError: If the destination directory or file cannot be written.
        """
        lines: List[str] = [
            f"# Quickbase App Schema: {schema.get('name')} (ID: {schema.get('app_id')})"
        ]

        description = schema.get("description")
        if description:
            lines.append(f"**Description:** {description}")
        lines.append("")

        lines.append("## Tables Overview")
        for table in schema["tables"]:
            field_count = len(table.get("fields", []))
            lines.append(
                f"- **{table.get('name')}** (ID: `{table.get('id')}`): {field_count} fields"
            )
        lines.append("")

        lines.append("## Detailed Database Schema")

        for table in schema["tables"]:
            lines.append(f"### Table: {table.get('name')} (ID: `{table.get('id')}`)")
            if table.get("plural_name"):
                lines.append(f"*Plural Name:* {table.get('plural_name')}")
            if table.get("description"):
                lines.append(f"*Description:* {table.get('description')}")
            lines.append("")

            lines.append("#### Fields List")
            lines.append("| Field ID | Label | Field Type | Details / Formula |")
            lines.append("|---|---|---|---|")

            for field in table["fields"]:
                details_parts = []
                if field.get("required"):
                    details_parts.append("Required")
                if field.get("unique"):
                    details_parts.append("Unique")
                if field.get("formula"):
                    details_parts.append(f"Formula: `{field['formula']}`")

                details = ", ".join(details_parts) if details_parts else "-"
                lines.append(
                    "| "
                    f"{self._markdown_cell(field.get('id'))} | "
                    f"**{self._markdown_cell(field.get('label'))}** | "
                    f"{self._markdown_cell(field.get('type'))} | "
                    f"{self._markdown_cell(details)} |"
                )
            lines.append("")

            relationships = table.get("relationships", [])
            if relationships:
                lines.append("#### Table Relationships (As Child Table)")
                for relationship in relationships:
                    parent = (
                        relationship.get("parent_table_name")
                        or relationship.get("parent_table_id")
                    )
                    reference_label = (
                        relationship.get("reference_field_label")
                        or "unnamed reference field"
                    )
                    lines.append(
                        f"- Links to parent table **{parent}** "
                        f"via reference field ID `{relationship.get('reference_field_id')}` "
                        f"({reference_label})."
                    )
                lines.append("")

            lines.append("---")
            lines.append("")

        md_str = "\n".join(lines)
        if filepath:
            path = Path(filepath)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(md_str, encoding="utf-8")
        return md_str
