# Examples

The repository includes a read-only schema export command and a PTO application demo. Both can
run directly from a source checkout.

## Export An Existing Schema

`examples/export_schema.py` reads an existing application and writes JSON and Markdown:

```powershell
$env:QUICKBASE_REALM_HOSTNAME = "example.quickbase.com"
$env:QUICKBASE_USER_TOKEN = "your-user-token"

.\.venv\Scripts\python.exe examples/export_schema.py --app-id "app-id"
```

Optional arguments:

| Argument | Purpose |
|---|---|
| `--app-id` | Required Quickbase application ID |
| `--table-id` | Optional table ID to export by itself |
| `--realm-hostname` | Overrides `QUICKBASE_REALM_HOSTNAME` |
| `--user-token` | Overrides `QUICKBASE_USER_TOKEN` |
| `--output-dir` | Output directory; defaults to `schema_exports` |

When `--table-id` is supplied, the command writes
`<app-id>_<table-id>_schema.json` and `<app-id>_<table-id>_schema.md`.

Do not put a token directly in shell history when an environment variable is available.

The command disables automatic backups because it performs only read operations.

## Preview The PTO Demo

Copy the sample settings:

```powershell
Copy-Item .env.example .env
```

Preview the ordered plan:

```powershell
.\.venv\Scripts\python.exe examples/pto_tracking_demo.py --env-file .env
```

Dry-run mode does not require valid credentials and does not contact Quickbase.

The plan can include:

- Creating a PTO tracking app.
- Assigning the current user token to the new app.
- Creating `Users` and `PTO Events` tables.
- Creating twelve fields across those tables.
- Creating an optional parent-child relationship.
- Adding an optional trustee.
- Exporting the resulting schema to JSON and Markdown.

## Execute The PTO Demo

Execution creates live Quickbase resources:

```powershell
.\.venv\Scripts\python.exe examples/pto_tracking_demo.py `
  --env-file .env `
  --execute
```

The script rejects the placeholder realm and token from `.env.example`. It prints created app
and table URLs so a partial run can be inspected if a later operation fails.

The relationship creation is best-effort in the demo: a package-level Quickbase failure is
printed and schema export continues. Other required Quickbase operations fail the run.

## PTO Demo Settings

Operating-system environment variables override values loaded from the selected `.env` file.

| Variable | Default | Purpose |
|---|---|---|
| `QUICKBASE_REALM_HOSTNAME` | `example.quickbase.com` | Target Quickbase realm |
| `QUICKBASE_USER_TOKEN` | Placeholder | User token used by the demo |
| `QUICKBASE_DEMO_EXECUTE` | `false` | Enables live operations |
| `QUICKBASE_DEMO_APP_NAME` | `PTO Tracking Demo` | New app name |
| `QUICKBASE_DEMO_ASSIGN_TOKEN` | `true` | Assigns the token to the new app |
| `QUICKBASE_DEMO_EXPORT_DIR` | `demo_exports` | Schema export directory |
| `QUICKBASE_DEMO_CREATE_RELATIONSHIP` | `true` | Attempts the table relationship |
| `QUICKBASE_DEMO_AUTO_BACKUP` | `false` | Enables mutation backups |
| `QUICKBASE_DEMO_BACKUP_METHOD` | `schema` | `schema` or `clone` |
| `QUICKBASE_DEMO_BACKUP_SOLUTION_ID` | Empty | Solution used for QBL backups |
| `QUICKBASE_DEMO_BACKUP_DIR` | `demo_backups` | Local QBL backup directory |
| `QUICKBASE_DEMO_BACKUP_FALLBACK_TO_CLONE` | `true` | Enables clone fallback |
| `QUICKBASE_DEMO_TRUSTEE_EMAIL` | Empty | Optional trustee email |
| `QUICKBASE_DEMO_TRUSTEE_ROLE_ID` | Empty | Optional trustee role ID |

Set both trustee variables to add the trustee. Setting only one causes the demo to skip trustee
creation.

Keep automatic backup disabled for the first live run unless the Solution ID and fallback
behavior have been verified. Clone fallback creates additional Quickbase applications.

## Common Failures

### User Token Is Invalid

Check all of the following:

- The realm is where the token was generated.
- The value is a user token, not an app token.
- The token value has no quotes, labels, or comments around it.
- The token owner can create apps in the realm.
- `QUICKBASE_DEMO_ASSIGN_TOKEN=true` so the token can access the new app.

### Field Description Is Rejected

Quickbase field help uses `fieldHelp`, not an API property named `description`. The client maps
`description` to `fieldHelp` in field create and update helpers:

```python
table.create_field(
    "Employee Name",
    "text",
    {"description": "Employee display name."},
)
```

### Partial Demo Application

The demo does not automatically delete a partially created app. Use the printed app URL to
inspect it. Delete it only after confirming the realm, app ID, and app name.
