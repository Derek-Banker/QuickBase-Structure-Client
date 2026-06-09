# Getting Started

QuickBase Structure Client is a synchronous Python 3.10+ client for Quickbase
administration and schema lifecycle work. It manages applications, tables, fields,
relationships, trustees, Solutions/QBL documents, schema exports, and automatic backups.

For record data, reports, files, or pandas workflows, use a data-focused client instead.

## Install

Install the published package:

```powershell
python -m pip install quickbase-structure-client
```

For repository development:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

## Configure Credentials

The client requires a Quickbase realm hostname and user token. Keep both values outside source
control.

```powershell
$env:QUICKBASE_REALM_HOSTNAME = "example.quickbase.com"
$env:QUICKBASE_USER_TOKEN = "your-user-token"
```

Create the authenticated client:

```python
import os

from quickbase_structure_client import Auth, QuickBaseStructureClient

auth = Auth(
    os.environ["QUICKBASE_REALM_HOSTNAME"],
    os.environ["QUICKBASE_USER_TOKEN"],
)
client = QuickBaseStructureClient(auth, auto_backup=False)
```

`Auth` accepts a realm URL or bare hostname. It also accepts a raw token or a value prefixed
with `QB-USER-TOKEN`. Empty normalized values raise `QuickbaseConfigurationError`.

`auto_backup=True` is the client default. The examples on this page disable it until backup
behavior has been deliberately configured. See [Automatic Backups](automatic-backups.md).

## Reference Existing Resources

Bound resource wrappers retain IDs and parent context:

```python
app = client.app("app-id", name="Operations")
table = app.table("table-id", name="Orders")
field = table.field(7, label="Total")
relationship = table.relationship(3)
```

Read-only operations do not trigger automatic backups:

```python
app_details = app.get_details()
tables = app.list_tables()
fields = table.list_fields(include_field_perms=True)
relationships = table.list_relationships()
```

Use `client.table(...)` when an application wrapper is not convenient:

```python
table = client.table("table-id", app_id="app-id", name="Orders")
```

Include `app_id` when constructing a table directly if you intend to update its structure.
Table, field, and relationship mutations need the parent application ID for automatic backup
orchestration.

## Create An Application Structure

The following calls create live Quickbase resources:

```python
app = client.create_app(
    "Managed Operations",
    description="Created by structural automation.",
    assign_token=True,
)

orders = app.create_table(
    "Order",
    plural_name="Orders",
    single_record_name="Order",
    description="Customer orders.",
)

total = orders.create_field(
    "Total",
    "currency",
    {"description": "Order total."},
)
```

For field creation and updates, `description` is a convenience alias for Quickbase
`fieldHelp`. If both keys are supplied, `fieldHelp` wins.

`assign_token=True` asks Quickbase to assign the current user token to the newly created app.
This can be required before the same token can create tables or fields in that app.

## Update Existing Structure

```python
app.update(description="Managed by the platform team.")
orders.update(plural_name="Customer Orders")
orders.update_field(total["id"], {"label": "Order Total"})

field = orders.field(total["id"])
field.update({"description": "Final order amount."})
```

These are structural mutations. When automatic backup is enabled and application context is
available, the client creates a pre-change backup, performs the request, and creates a
post-change backup.

## Destructive Operations

Deletion calls affect live Quickbase structure:

```python
orders.delete_fields([7, 8])
orders.delete_relationship(3)
orders.delete()
client.delete_app("app-id", confirm_name="Managed Operations")
```

Application deletion requires the exact application name as a confirmation payload. Field
deletion sends integer field IDs in Quickbase's `{"fieldIds": [...]}` shape.

Before running a deletion:

1. Confirm the target realm, app ID, and table ID.
2. Verify the current token has the intended administrative permissions.
3. Configure and test backups, or explicitly accept running with `auto_backup=False`.

## Handle Errors

Catch `QuickbaseError` for package-level failures, or catch a specific subclass:

```python
from quickbase_structure_client import (
    QuickbaseAuthError,
    QuickbaseError,
    QuickbaseRateLimitError,
)

try:
    app.get_details()
except QuickbaseAuthError:
    print("Check the realm, token assignment, and permissions.")
except QuickbaseRateLimitError:
    print("Quickbase continued to rate limit after configured retries.")
except QuickbaseError as exc:
    print(f"Quickbase operation failed: {exc}")
```

The request layer maps terminal HTTP and transport failures to package exceptions. It redacts
the configured user token from error response previews.

## Next Steps

- [API Reference](api-reference.md)
- [Request Configuration](request-configuration.md)
- [Automatic Backups](automatic-backups.md)
- [Schema Exports and Solutions](schema-exports-and-solutions.md)
- [Examples](examples.md)
