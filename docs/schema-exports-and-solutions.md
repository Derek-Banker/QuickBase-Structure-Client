# Schema Exports And Solutions

The package provides two distinct schema workflows:

- `SchemaExporter` compiles selected application metadata through app, table, field, and
  relationship endpoints, then renders JSON or Markdown.
- `SolutionsManager` sends and receives raw Quickbase QBL documents.

They are not interchangeable. A compiled schema is a readable structural inventory, while QBL
is a Quickbase Solution document.

## Compile An Application Schema

```python
from quickbase_structure_client import Auth, QuickBaseStructureClient

client = QuickBaseStructureClient(
    Auth("example.quickbase.com", "user-token"),
    auto_backup=False,
)

schema = client.exporter.compile_schema("b12345678")
```

To compile only one table, pass its ID:

```python
schema = client.exporter.compile_schema(
    "b12345678",
    table_id="b23456789",
)
```

The single-table form fetches that table directly instead of listing and compiling every table.
It returns the same schema shape with exactly one item in `tables`, so the JSON and Markdown
renderers work without special handling.

The result has this shape:

```json
{
  "app_id": "b12345678",
  "name": "Operations",
  "description": "Managed application",
  "tables": [
    {
      "id": "b23456789",
      "name": "Orders",
      "plural_name": "Orders",
      "description": "Customer orders",
      "fields": [
        {
          "id": 7,
          "label": "Total",
          "type": "currency",
          "formula": null,
          "choices": null,
          "queries": {},
          "unique": false,
          "required": false,
          "properties": {}
        }
      ],
      "relationships": [
        {
          "relationship_id": 3,
          "parent_table_id": "b34567890",
          "parent_table_name": "Customers",
          "reference_field_id": 12,
          "reference_field_label": "Customer",
          "summary_fields": []
        }
      ]
    }
  ]
}
```

Relationships are listed for tables acting as child tables. The exporter includes application
metadata, table metadata, field IDs, labels, types, formulas, choice lists, query-like field
properties, unique/required flags, the raw field `properties` dictionary returned by
Quickbase, selected relationship metadata, and relationship `summaryFields` data. It is still
not a complete serialization of every Quickbase setting.

Quickbase authorizes relationship metadata separately from app, table, and field reads. A user
token can therefore read most of an app but receive HTTP 403 for a particular table's
relationship endpoint. Ensure the user associated with the token has sufficient structural
permissions for every exported table. For cross-application relationships, also verify that
user's access to the related applications.

If a table lacks an ID, or field or relationship retrieval fails, compilation raises
`QuickbaseSchemaError`. Permission, authentication, rate-limit, not-found, and transport
failures receive distinct summaries. Inspect `error.context` for the app, table, and resource,
and `error.cause` for the original package exception such as `QuickbasePermissionError`. The
exporter does not silently return a partial schema.

## Render JSON Or Markdown

Return rendered text without writing a file:

```python
json_text = client.exporter.to_json(schema)
markdown_text = client.exporter.to_markdown(schema)
```

Write output files and receive the same rendered text:

```python
from pathlib import Path

client.exporter.to_json(schema, Path("exports/app_schema.json"))
client.exporter.to_markdown(schema, Path("exports/app_schema.md"))
```

Parent directories are created automatically. Generated Markdown escapes pipes, backslashes,
and newlines used in table cells. Field details show formulas, choices, and query-like
properties when Quickbase returns them.

## Schema Export Command

The repository includes a command-line example:

```powershell
$env:QUICKBASE_REALM_HOSTNAME = "example.quickbase.com"
$env:QUICKBASE_USER_TOKEN = "your-user-token"
.\.venv\Scripts\python.exe examples/export_schema.py --app-id "b12345678"
```

The default output files are:

```text
schema_exports/<app-id>_schema.json
schema_exports/<app-id>_schema.md
```

Choose another directory with `--output-dir`:

```powershell
.\.venv\Scripts\python.exe examples/export_schema.py `
  --app-id "b12345678" `
  --output-dir "exports"
```

Export one table with `--table-id`:

```powershell
.\.venv\Scripts\python.exe examples/export_schema.py `
  --app-id "b12345678" `
  --table-id "b23456789"
```

Single-table files are named `<app-id>_<table-id>_schema.json` and
`<app-id>_<table-id>_schema.md`.

The script is read-only against Quickbase and constructs the client with `auto_backup=False`.

## Export QBL

Return QBL text:

```python
qbl = client.solutions.export_solution(
    "solution-id",
    qbl_version="0.9",
)
```

Write QBL to a local file:

```python
path = client.solutions.export_solution_to_file(
    "solution-id",
    "exports/solution.qbl",
    qbl_version="0.9",
)
```

When supplied, `qbl_version` is sent in the `QBL-Version` request header.

## Create A Solution

QBL must be a non-empty string:

```python
from pathlib import Path

qbl = Path("solution.qbl").read_text(encoding="utf-8")
result = client.solutions.create_solution(qbl)
```

The document is sent as raw request data with `Content-Type: application/x-yaml`. It is not
JSON encoded.

To ask Quickbase to return QBL processing errors as successful HTTP responses:

```python
result = client.solutions.create_solution(
    qbl,
    errors_as_success=True,
)
```

This adds `X-QBL-Errors-As-Success: true`. Callers must inspect the returned payload for QBL
errors when using this option.

## Update A Solution

`update_solution` sends a complete QBL document to an existing Solution.
It sends raw YAML with `PUT /solutions/{solution_id}`.
It does not merge a partial document with the current Solution.

CAUTION: Preserve the complete exported document and its logical IDs before you apply changes.
Omitted resources can be deleted. A compiled JSON schema is not an update document.

The package's QBL and clone backups preserve structure only.
Clone backups use `keep_data=False` and `exclude_files=True`.
These backups cannot recover deleted records or attachments.

1. Export the target Solution with `export_solution` or `export_solution_to_file`.
2. Edit the exported QBL with the intended property changes.
3. Request a preview of the changes:

```python
from pathlib import Path

qbl = Path("exports/reviewed-solution.qbl").read_text(encoding="utf-8")
changes = client.solutions.preview_solution_changes("solution-id", qbl)
print(changes)
```

4. Review the response, especially proposed deletions and errors.
5. Review the complete document and the target Solution ID.
6. Supply every affected application ID for automatic backups.
7. Apply the reviewed document:

```python
result = client.solutions.update_solution(
    "solution-id",
    qbl,
    app_ids_for_backup=["b12345678"],
)
```

`preview_solution_changes` calls Quickbase's
[`List solution changes`](https://developer.quickbase.com/operation/changesetSolution) endpoint.
It sends raw YAML with `PUT /solutions/{solution_id}/changeset`.
The preview does not apply changes, create backups, or call `update_solution`.
The caller reviews the returned response before a separate update call.

With `auto_backup=True`, `app_ids_for_backup` must contain at least one application ID.
The caller supplies every affected app because the client does not parse QBL to discover them.
The client removes duplicate IDs and creates all pre-change backups before the update.
After a successful request, it creates the post-change backups.

Solution updates automatically use the target Solution ID for schema backups.
The same target remains in effect for both pre-change and post-change exports.
The client's global `backup_solution_id` remains unchanged for other operations.
See [Automatic Backups](automatic-backups.md) for schema backup configuration.

For previews and updates, `errors_as_success=True` adds the same header as `create_solution`.
With this option, callers must inspect the result for QBL errors.
The client passes QBL through to Quickbase without local schema validation.

### Table Sorting And Choice Sources

QBL exposes properties that the REST table and field update endpoints do not accept.
The following paths refer to QBL v0.12:

| Purpose | QBL property |
|---|---|
| Default table sort field | `DefaultReportSettings.DefaultSortOrder.TargetField` |
| Default table sort direction | `DefaultReportSettings.DefaultSortOrder.SortOrder` (`Ascending` or `Descending`) |
| Field choice source | `InputOptions.Target` on supported field types |

These paths belong inside a complete exported QBL document. References use the document's
logical IDs. They are not REST field IDs or partial update payloads.
The available properties depend on the QBL version and field type.
See Quickbase's [table properties](https://help.quickbase.com/docs/tables-qbl-v012) and
[field properties](https://help.quickbase.com/docs/field-properties-qbl-v012).

## Export QBL To A Record

Export a Solution to a Quickbase file attachment field:

```python
result = client.solutions.export_solution_to_record(
    "solution-id",
    "b23456789",
    12,
    record_id=4,
    qbl_version="0.9",
)
```

Omit `record_id` to let Quickbase create the destination record. `solution_id`, `table_id`, and
`field_id` are required.

## Backup Relationship

Automatic schema backups call `SolutionsManager.export_solution(...)` before and after
structural mutations. The backup manager writes that QBL to local files. See
[Automatic Backups](automatic-backups.md) for configuration and fallback behavior.
