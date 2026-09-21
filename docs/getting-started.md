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
Internal whitespace, control characters, and non-ASCII characters in the normalized token raise
the same error before a request.

`auto_backup=True` is the client default. The examples on this page disable it until backup
behavior has been deliberately configured. See [Automatic Backups](automatic-backups.md).

## Reference Existing Resources

Bound resource wrappers retain IDs and parent context.

Replace the sample IDs with IDs from your Quickbase app.

```python
app = client.app("b12345678", name="Operations")
table = app.table("b23456789", name="Orders")
field = table.field(7, label="Total")
relationship = table.relationship(3)
```

Table and application IDs must contain only ASCII letters and digits.
Field IDs must be positive integers or strings of ASCII decimal digits.
The client validates IDs before the relevant request or backup.
Wrapper construction does not validate IDs.

Read-only operations do not trigger automatic backups:

```python
app_details = app.get_details()
tables = app.list_tables()
fields = table.list_fields(include_field_perms=True)
field_usage = table.get_fields_usage(skip=0, top=100)
total_usage = field.get_usage()
relationships = table.list_relationships()
```

Use `client.table(...)` when an application wrapper is not convenient:

```python
table = client.table("b23456789", app_id="b12345678", name="Orders")
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
    options={"description": "Order total."},
)
```

For field creation and updates, `description` is a convenience alias for Quickbase
`fieldHelp`. If both keys are supplied, `fieldHelp` wins.

The `options` argument contains the whole field request body. Type-specific properties
belong in its nested `properties` dictionary:

```python
status = orders.create_field(
    "Status",
    "text-multiple-choice",
    options={
        "properties": {
            "choices": ["Pending", "Approved"],
            "allowNewChoices": False,
        },
    },
)
orders.update_field(status["id"], options={"required": True})
```

The REST creation endpoint does not accept `required` or `unique`.
Set those options through an update after field creation.

Existing positional calls and the legacy `properties=` keyword still work.
Use `options=` for new code. Supplying both keywords raises `QuickbaseValidationError`.

`assign_token=True` asks Quickbase to assign the current user token to the newly created app.
This can be required before the same token can create tables or fields in that app.

## Update Existing Structure

```python
app.update(description="Managed by the platform team.")
orders.update(plural_name="Customer Orders")
orders.update_field(total["id"], options={"label": "Order Total"})

field = orders.field(total["id"])
field.update(options={"description": "Final order amount."})
```

These are structural mutations. When automatic backup is enabled and application context is
available, the client creates a pre-change backup, performs the request, and creates a
post-change backup.

Some properties require the XML API:

```python
field.update_xml({"doesdatacopy": False})
order_number = orders.create_field(
    "Order Number",
    "text",
)
orders.update_field(order_number["id"], options={"unique": True, "required": True})
orders.set_key_field(order_number["id"])
```

The key field must meet Quickbase's uniqueness and field-type requirements.
If the app requires an application token, pass `app_token=` to either XML method.
The client uses its existing user token for authentication.
See [XML field updates](api-reference.md#xml-field-updates) for the supported workflow.

Default table sorting and choice-source references use
[Solution updates through QBL](schema-exports-and-solutions.md#update-a-solution).
Existing field type conversion remains unsupported.

## Destructive Operations

Deletion calls affect live Quickbase structure:

```python
orders.delete_fields([7, 8])
orders.delete_relationship(3)
orders.delete()
client.delete_app("b12345678", confirm_name="Managed Operations")
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
    QuickbasePermissionError,
    QuickbaseRateLimitError,
)

try:
    app.get_details()
except QuickbasePermissionError:
    print("The token is valid, but its user lacks permission for this resource.")
except QuickbaseAuthError:
    print("Check the realm hostname and user token.")
except QuickbaseRateLimitError:
    print("Quickbase continued to rate limit after configured retries.")
except QuickbaseError as exc:
    print(f"Quickbase operation failed: {exc}")
```

The request layer maps terminal HTTP and transport failures to package exceptions. Catch
`QuickbasePermissionError` before `QuickbaseAuthError` because it is a more specific subclass.
Exceptions expose structured `context`, and wrapper exceptions expose their translated
`cause`. The configured user token is redacted from error response previews.

## Next Steps

- [API Reference](api-reference.md)
- [Request Configuration](request-configuration.md)
- [Automatic Backups](automatic-backups.md)
- [Schema Exports and Solutions](schema-exports-and-solutions.md)
- [Examples](examples.md)
