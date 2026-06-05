# Walkthrough

This walkthrough uses mock-safe examples. Use a staging Quickbase realm before
running destructive operations against a real tenant.

## 1. Configure Auth

```python
from quickbase_structure_client import Auth, QuickBaseStructureClient

auth = Auth("example.quickbase.com", "qb-user-token")
client = QuickBaseStructureClient(auth, auto_backup=False)
```

Set `auto_backup=False` while experimenting. Turn it back on when you have a
valid backup strategy.

## 2. Create an App and Table

```python
app = client.create_app("Managed Operations", description="Automation test app")

orders = app.create_table(
    "Order",
    plural_name="Orders",
    single_record_name="Order",
    description="Customer order records",
)
```

## 3. Add and Update Fields

```python
orders.create_field("Order Number", "text", {"required": True, "unique": True})
total = orders.create_field("Total", "currency")

orders.update_field(
    total["id"],
    {
        "label": "Total",
        "fieldType": "formula-numeric",
        "properties": {"formula": "[Subtotal] + [Tax]"},
    },
)
```

You can also use a field reference:

```python
field = orders.field(total["id"], label="Total")
field.update({"description": "Calculated order total"})
```

## 4. Manage Relationships

```python
orders.create_relationship(
    {
        "parentTableId": "customers-table-id",
        "foreignKeyField": {"label": "Customer"},
        "lookupFieldIds": [6, 7],
        "summaryFields": [],
    }
)
```

Existing relationships can be updated or deleted from a table wrapper:

```python
orders.update_relationship(1, {"lookupFieldIds": [6, 7, 8]})
orders.delete_relationship(1)
```

## 5. Manage Trustees

```python
app.add_trustees(
    [
        {
            "id": "user@example.com",
            "type": "user",
            "roleId": 12,
        }
    ]
)

app.update_trustees(
    [
        {
            "id": "user@example.com",
            "type": "user",
            "roleId": 13,
        }
    ]
)

app.remove_trustees([{"id": "user@example.com", "type": "user"}])
```

## 6. Export Schema

```python
schema = client.exporter.compile_schema(app.id)

client.exporter.to_json(schema, "exports/schema.json")
client.exporter.to_markdown(schema, "exports/schema.md")
```

## 7. Enable Backups

Schema backup through Solutions/QBL:

```python
client = QuickBaseStructureClient(
    auth,
    auto_backup=True,
    backup_method="schema",
    backup_solution_id="solution-id",
    backup_dir="backups",
)
```

Clone backup:

```python
client = QuickBaseStructureClient(
    auth,
    auto_backup=True,
    backup_method="clone",
)
```

The client suppresses backup hooks while it is performing backup operations, so
clone-based backups do not recursively clone themselves.

## 8. Validate Locally

```bash
pytest
python -m compileall src tests examples
python -m ruff check src tests examples
```

## 9. Run the PTO Demo

The PTO demo creates a small app with `Users` and `PTO Events` tables.

```bash
copy .env.example .env
python examples/pto_tracking_demo.py --env-file .env
```

The first command creates a local `.env` file. Fill in real
`QUICKBASE_REALM_HOSTNAME` and `QUICKBASE_USER_TOKEN` values before executing.

```bash
python examples/pto_tracking_demo.py --env-file .env --execute
```

The demo defaults to dry-run mode. It only creates a live Quickbase app when
`--execute` is passed or `QUICKBASE_DEMO_EXECUTE=true` is set.
