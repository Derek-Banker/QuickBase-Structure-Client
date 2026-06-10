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

schema = client.exporter.compile_schema("app-id")
```

To compile only one table, pass its ID:

```python
schema = client.exporter.compile_schema(
    "app-id",
    table_id="table-id",
)
```

The single-table form fetches that table directly instead of listing and compiling every table.
It returns the same schema shape with exactly one item in `tables`, so the JSON and Markdown
renderers work without special handling.

Full application exports can issue many requests. The exporter spaces schema lookups by 0.11
seconds by default to remain below
[Quickbase's general limit](https://developer.quickbase.com/rateLimit) of 100 API calls per 10
seconds per user token. Override the interval when needed:

```python
schema = client.exporter.compile_schema(
    "app-id",
    request_interval=0.2,
)
```

Set `request_interval=0` only when pacing is handled elsewhere.

The result has this shape:

```json
{
  "app_id": "app-id",
  "name": "Operations",
  "description": "Managed application",
  "tables": [
    {
      "id": "table-id",
      "name": "Orders",
      "plural_name": "Orders",
      "description": "Customer orders",
      "fields": [
        {
          "id": 7,
          "label": "Total",
          "type": "currency",
          "formula": null,
          "unique": false,
          "required": false
        }
      ],
      "relationships": [
        {
          "relationship_id": 3,
          "parent_table_id": "parent-table-id",
          "parent_table_name": "Customers",
          "reference_field_id": 12,
          "reference_field_label": "Customer"
        }
      ]
    }
  ]
}
```

Relationships are listed for tables acting as child tables. The exporter includes application
metadata, table metadata, field IDs, labels, types, formulas, unique/required flags, and
selected relationship metadata. It is not a complete serialization of every Quickbase
setting.

If a table lacks an ID, or field or relationship retrieval fails, compilation raises
`QuickbaseSchemaError`. The error includes the underlying failure cause, and the exporter does
not silently return a partial schema.

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
and newlines used in table cells.

## Schema Export Command

The repository includes a command-line example:

```powershell
$env:QUICKBASE_REALM_HOSTNAME = "example.quickbase.com"
$env:QUICKBASE_USER_TOKEN = "your-user-token"
.\.venv\Scripts\python.exe examples/export_schema.py --app-id "app-id"
```

The default output files are:

```text
schema_exports/<app-id>_schema.json
schema_exports/<app-id>_schema.md
```

Choose another directory with `--output-dir`:

```powershell
.\.venv\Scripts\python.exe examples/export_schema.py `
  --app-id "app-id" `
  --output-dir "exports"
```

Export one table with `--table-id`:

```powershell
.\.venv\Scripts\python.exe examples/export_schema.py `
  --app-id "app-id" `
  --table-id "table-id"
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

## Export QBL To A Record

Export a Solution to a Quickbase file attachment field:

```python
result = client.solutions.export_solution_to_record(
    "solution-id",
    "table-id",
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
