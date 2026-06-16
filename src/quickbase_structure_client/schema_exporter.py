"""Utilities for exporting Quickbase application schemas."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List

from quickbase_structure_client.exceptions import (
    QuickbaseAuthError,
    QuickbaseHTTPError,
    QuickbaseNotFoundError,
    QuickbasePermissionError,
    QuickbaseRateLimitError,
    QuickbaseSchemaError,
    QuickbaseTransportError,
    QuickbaseValidationError,
    format_error_message,
)

if TYPE_CHECKING:
    from quickbase_structure_client.quickbase_api import QuickBaseStructureClient
    from quickbase_structure_client.table import StructureTable

logger = logging.getLogger(__name__)


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
    def _has_detail_value(value: Any) -> bool:
        """Return whether a value should be rendered as schema detail.

        Args:
            value: Value to inspect.

        Returns:
            ``True`` when the value contains visible detail.
        """
        return value is not None and value != "" and value != [] and value != {}

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

    @staticmethod
    def _copy_mapping(value: Any) -> Dict[str, Any]:
        """Return a shallow copy when ``value`` is a dictionary.

        Args:
            value: Candidate mapping value.

        Returns:
            A copied dictionary, or an empty dictionary for non-dictionaries.
        """
        if isinstance(value, dict):
            return dict(value)
        return {}

    @classmethod
    def _extract_field_choices(cls, properties: Dict[str, Any]) -> Any:
        """Extract field choices from Quickbase field properties.

        Args:
            properties: Field ``properties`` dictionary returned by Quickbase.

        Returns:
            The choices value when present, otherwise ``None``.
        """
        choices = properties.get("choices")
        if cls._has_detail_value(choices):
            return choices
        return None

    @classmethod
    def _extract_query_values(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Extract query-like values while preserving Quickbase key names.

        Args:
            values: Metadata dictionary returned by Quickbase.

        Returns:
            Query-like key/value pairs, such as ``query``, ``where``, or
            ``summaryQuery``.
        """
        query_values: Dict[str, Any] = {}
        for key, value in values.items():
            normalized_key = key.lower()
            if not cls._has_detail_value(value):
                continue
            if (
                "query" in normalized_key
                or "criteria" in normalized_key
                or normalized_key == "where"
            ):
                query_values[key] = value
        return query_values

    @classmethod
    def _format_detail_value(cls, value: Any) -> str:
        """Format a schema detail value for compact Markdown rendering.

        Args:
            value: Detail value to format.

        Returns:
            A readable string representation.
        """
        if isinstance(value, list):
            return "; ".join(cls._format_detail_value(item) for item in value)
        if isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        return str(value)

    @classmethod
    def _format_query_details(cls, queries: Dict[str, Any]) -> str:
        """Format query-like values for Markdown details.

        Args:
            queries: Query-like key/value pairs.

        Returns:
            A compact query detail string.
        """
        if len(queries) == 1:
            return cls._format_detail_value(next(iter(queries.values())))
        return "; ".join(
            f"{key}={cls._format_detail_value(value)}" for key, value in queries.items()
        )

    def _field_detail_parts(self, field: Dict[str, Any]) -> List[str]:
        """Build Markdown details for a compiled field.

        Args:
            field: Field schema entry produced by :meth:`compile_schema`.

        Returns:
            Ordered detail fragments.
        """
        details_parts = []
        if field.get("required"):
            details_parts.append("Required")
        if field.get("unique"):
            details_parts.append("Unique")
        if field.get("formula"):
            details_parts.append(f"Formula: `{field['formula']}`")
        if self._has_detail_value(field.get("choices")):
            choices = self._format_detail_value(field["choices"])
            details_parts.append(f"Choices: {choices}")

        queries = self._copy_mapping(field.get("queries"))
        if queries:
            details_parts.append(f"Query: `{self._format_query_details(queries)}`")

        return details_parts

    def _relationship_summary_details(self, summary_field: Dict[str, Any]) -> str:
        """Build Markdown details for a relationship summary field.

        Args:
            summary_field: Summary field metadata returned by Quickbase.

        Returns:
            A compact Markdown sentence fragment.
        """
        summary_id = (
            summary_field.get("summaryFid")
            or summary_field.get("summaryFieldId")
            or summary_field.get("fieldId")
            or "unknown"
        )
        details = [f"summary field ID `{summary_id}`"]

        label = summary_field.get("label") or summary_field.get("summaryFieldLabel")
        if label:
            details.append(str(label))

        queries = self._extract_query_values(summary_field)
        if queries:
            details.append(f"Query: `{self._format_query_details(queries)}`")

        return " - ".join(details)

    def _compile_table(
        self,
        app_id: str,
        table_info: Dict[str, Any],
        table_ref: StructureTable,
    ) -> Dict[str, Any]:
        """Compile one table's fields and child relationships.

        Args:
            app_id: Parent Quickbase application ID.
            table_info: Table metadata returned by Quickbase.
            table_ref: Bound table reference used for child lookups.

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
            for field_info in table_ref.list_fields():
                properties = self._copy_mapping(field_info.get("properties"))
                table_schema["fields"].append(
                    {
                        "id": field_info.get("id"),
                        "label": field_info.get("label"),
                        "type": field_info.get("fieldType"),
                        "formula": properties.get("formula"),
                        "choices": self._extract_field_choices(properties),
                        "queries": self._extract_query_values(properties),
                        "unique": field_info.get(
                            "unique",
                            properties.get("unique", False),
                        ),
                        "required": field_info.get(
                            "required",
                            properties.get("required", False),
                        ),
                        "properties": properties,
                    }
                )
        except Exception as exc:
            self._raise_lookup_error(
                resource="field metadata",
                app_id=app_id,
                table_id=table_id,
                cause=exc,
            )

        try:
            for relationship in table_ref.list_relationships():
                table_schema["relationships"].append(
                    {
                        "relationship_id": relationship.get("id"),
                        "parent_table_id": relationship.get("parentTableId"),
                        "parent_table_name": relationship.get("parentTableName"),
                        "reference_field_id": relationship.get("referenceFieldId"),
                        "reference_field_label": relationship.get("referenceFieldLabel"),
                        "summary_fields": relationship.get("summaryFields") or [],
                    }
                )
        except Exception as exc:
            self._raise_lookup_error(
                resource="relationship metadata",
                app_id=app_id,
                table_id=table_id,
                cause=exc,
            )

        return table_schema

    @staticmethod
    def _raise_lookup_error(
        *,
        resource: str,
        app_id: str,
        table_id: str,
        cause: BaseException,
    ) -> None:
        """Raise a contextual schema lookup failure.

        Args:
            resource: Schema resource that could not be retrieved.
            app_id: Parent Quickbase application ID.
            table_id: Quickbase table ID being compiled.
            cause: Underlying lookup failure.

        Raises:
            QuickbaseSchemaError: Always raised with structured context.
        """
        if isinstance(cause, QuickbasePermissionError):
            summary = (
                f"Quickbase denied access to {resource} while compiling the schema. "
                "Verify the user token's user has sufficient structural permissions."
            )
        elif isinstance(cause, QuickbaseAuthError):
            summary = (
                f"Quickbase authentication failed while fetching {resource}. "
                "Verify the realm hostname and user token."
            )
        elif isinstance(cause, QuickbaseRateLimitError):
            summary = f"Quickbase rate limiting prevented retrieval of {resource}."
        elif isinstance(cause, QuickbaseNotFoundError):
            summary = f"Quickbase could not find the requested {resource}."
        elif isinstance(cause, QuickbaseTransportError):
            summary = f"A network or timeout failure prevented retrieval of {resource}."
        elif isinstance(cause, QuickbaseHTTPError):
            summary = f"Quickbase rejected the request for {resource}."
        else:
            summary = f"Failed to fetch {resource} while compiling the schema."

        context = {
            "operation": "SchemaExporter.compile_schema",
            "app_id": app_id,
            "table_id": table_id,
            "resource": resource,
        }
        raise QuickbaseSchemaError(
            format_error_message(
                summary,
                **context,
                cause=cause,
            ),
            context=context,
            cause=cause,
        ) from cause

    def compile_schema(
        self,
        app_id: str,
        *,
        table_id: str | None = None,
    ) -> Dict[str, Any]:
        """Compile an application's structural schema.

        The compiled schema contains application metadata, tables, fields,
        formulas, field choices, query-like field properties, raw field
        properties, and relationships for which each table is the child. When
        ``table_id`` is supplied, only that table is compiled.

        Args:
            app_id: Quickbase application ID.
            table_id: Optional Quickbase table ID to compile by itself.

        Returns:
            A dictionary containing the compiled application schema. A
            single-table export retains the same shape with one item in
            ``tables``.

        Raises:
            QuickbaseValidationError: If ``table_id`` is empty.
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

        logger.info(
            "Compiling schema structure for app %s%s",
            app_id,
            f", table {table_id}" if table_id is not None else "",
        )

        app_ref = self.api_client.app(id=app_id)
        app_details = app_ref.get_details()

        schema: Dict[str, Any] = {
            "app_id": app_id,
            "name": app_details.get("name"),
            "description": app_details.get("description"),
            "tables": [],
        }

        if table_id is not None:
            table_ref = app_ref.table(id=table_id)
            table_info = dict(table_ref.get_details())
            table_info["id"] = table_id
            schema["tables"].append(self._compile_table(app_id, table_info, table_ref))
            return schema

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
            schema["tables"].append(self._compile_table(app_id, table_info, table_ref))

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
            lines.append("| Field ID | Label | Field Type | Details |")
            lines.append("|---|---|---|---|")

            for field in table["fields"]:
                details_parts = self._field_detail_parts(field)
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
                    summary_fields = relationship.get("summary_fields", [])
                    if summary_fields:
                        summary_details = [
                            self._relationship_summary_details(summary_field)
                            for summary_field in summary_fields
                            if isinstance(summary_field, dict)
                        ]
                        if summary_details:
                            lines.append(
                                f"  - Summary fields: {'; '.join(summary_details)}."
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
