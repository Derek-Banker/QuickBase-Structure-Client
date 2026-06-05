from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from quickbase_structure_client.quickbase_api import QuickBaseStructureClient

logger = logging.getLogger(__name__)


class SchemaExporter:
    """Export Quickbase application schemas as JSON or Markdown."""

    def __init__(self, api_client: QuickBaseStructureClient):
        self.api_client = api_client

    @staticmethod
    def _markdown_cell(value: Any) -> str:
        if value is None:
            return ""
        return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")

    def compile_schema(self, app_id: str) -> Dict[str, Any]:
        """
        Compile app details, tables, fields, formulas, and child-table relationships.
        """
        logger.info("Compiling schema structure for app: %s", app_id)

        app_ref = self.api_client.app(id=app_id)
        app_details = app_ref.get_details()

        schema: Dict[str, Any] = {
            "app_id": app_id,
            "name": app_details.get("name"),
            "description": app_details.get("description"),
            "tables": [],
        }

        for table_info in app_ref.list_tables():
            table_id = table_info.get("id")
            if table_id is None:
                logger.warning("Skipping table without an id while exporting app %s.", app_id)
                continue
            table_id = str(table_id)
            table_schema: Dict[str, Any] = {
                "id": table_id,
                "name": table_info.get("name"),
                "plural_name": table_info.get("pluralRecordName") or table_info.get("pluralName"),
                "description": table_info.get("description"),
                "fields": [],
                "relationships": [],
            }

            table_ref = app_ref.table(id=table_id)
            try:
                for field_info in table_ref.list_fields():
                    properties = field_info.get("properties", {})
                    table_schema["fields"].append(
                        {
                            "id": field_info.get("id"),
                            "label": field_info.get("label"),
                            "type": field_info.get("fieldType"),
                            "formula": properties.get("formula"),
                            "unique": properties.get("unique", False),
                            "required": properties.get("required", False),
                        }
                    )
            except Exception as exc:
                logger.error("Failed to fetch fields for table %s: %s", table_id, exc)

            try:
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
                logger.debug("Failed to fetch relationships for table %s: %s", table_id, exc)

            schema["tables"].append(table_schema)

        return schema

    def to_json(self, schema: Dict[str, Any], filepath: str | Path | None = None) -> str:
        """Serialize compiled schema to a pretty-printed JSON string and optionally a file."""
        json_str = json.dumps(schema, indent=2, ensure_ascii=False)
        if filepath:
            path = Path(filepath)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json_str, encoding="utf-8")
        return json_str

    def to_markdown(self, schema: Dict[str, Any], filepath: str | Path | None = None) -> str:
        """Format a compiled schema as hierarchical Markdown."""
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
