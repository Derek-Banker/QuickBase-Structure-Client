# QuickBase-Structure-Client

Python client for Quickbase structural administration: apps, tables, fields,
relationships, trustees, Solutions/QBL exports, and schema snapshots.

This package is intended to pair with `quickbase-data-client`. The data client
handles records, reports, files, and pandas workflows. This structure client
focuses on administration and schema lifecycle work.

## Installation

```bash
pip install quickbase-structure-client
```

For local development:

```bash
python -m pip install -e ".[dev]"
pytest
```

## Quickstart

```python
from quickbase_structure_client import Auth, QuickBaseStructureClient

auth = Auth("example.quickbase.com", "qb-user-token")
client = QuickBaseStructureClient(auth, auto_backup=False)

app = client.create_app("Managed Operations", description="Built by automation")
orders = app.create_table(
    "Order",
    plural_name="Orders",
    single_record_name="Order",
)

orders.create_field(
    "Total",
    "currency",
    {"description": "Order total"},
)

schema = client.exporter.compile_schema(app.id)
print(client.exporter.to_markdown(schema))
```

## Auto Backup

`auto_backup=True` is the default. Mutating app/table/field/relationship/trustee
calls trigger a pre-change and post-change backup.

```python
client = QuickBaseStructureClient(
    auth,
    auto_backup=True,
    backup_method="schema",
    backup_solution_id="solution-id",
    backup_dir="backups",
)
```

If `backup_method="schema"` has no `backup_solution_id` and fallback is enabled,
the client falls back to app cloning. Internal backup calls suppress their own
backup hooks to avoid recursive clone storms.

## PTO Demo

The demo script builds a small PTO tracking app with a `Users` table, a
`PTO Events` table, fields, an optional relationship, optional trustee access,
and schema exports.

Copy the sample environment file and fill in real Quickbase credentials:

```bash
copy .env.example .env
```

Preview the plan without creating anything:

```bash
python examples/pto_tracking_demo.py --env-file .env
```

Create the live Quickbase app:

```bash
python examples/pto_tracking_demo.py --env-file .env --execute
```

You can also set `QUICKBASE_DEMO_EXECUTE=true` in `.env`. The script refuses to
execute with placeholder credentials from `.env.example`.

If Quickbase returns `User token is invalid`, verify that:

- `QUICKBASE_REALM_HOSTNAME` is the same realm where the token was generated.
- `QUICKBASE_USER_TOKEN` is a user token, not an app token.
- `QUICKBASE_DEMO_ASSIGN_TOKEN=true` when creating a new demo app. User tokens
  are scoped to assigned apps, so a token can create an app but still fail on
  table/field calls unless it is assigned to that new app.
- The value has no quotes, comments, or copied label text around it.
- The token's user has permission to create apps in that realm.

## Supported Surface

- Core sync client: `QuickBaseStructureClient`
- Request tuning: `RequestConfig`
- App wrapper: `StructureApp`
- Table wrapper: `StructureTable`
- Field wrapper: `StructureField`
- Relationship wrapper: `StructureRelationship`
- Trustee manager: `TrusteesManager`
- Solutions/QBL manager: `SolutionsManager`
- Schema exporter: `SchemaExporter`

## Notes

- Python 3.10+ is required.
- Tests are mock-based and validate payload/method composition plus local backup
  behavior. They do not prove live tenant permissions or endpoint availability.
- Destructive app deletion requires the app name as confirmation because the
  Quickbase API requires that confirmation payload.

## License

Apache License 2.0. See [LICENSE](LICENSE).
