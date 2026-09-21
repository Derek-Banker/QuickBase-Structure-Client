# Automatic Backups

`QuickBaseStructureClient` can create backups immediately before and after structural
mutations. Automatic backup is enabled by default.

Backups can create Quickbase applications or write QBL files. Treat clone backups as
potentially billable and verify tenant limits before enabling them.

QBL and clone backups preserve structure only. Clone backups exclude records and attachments.
These backups cannot recover data deleted by a structural mutation.

## Trigger Rules

A backup runs only when all of the following are true:

- `auto_backup=True`.
- The request method is `POST`, `PUT`, `PATCH`, or `DELETE`.
- The wrapper supplies `app_id_for_backup` or a nonempty `app_ids_for_backup` list.
- Backup suppression is not active.

Read-only requests do not trigger backups. Creating a new app does not have an existing app ID
to back up, so the app creation request itself is not surrounded by backups.
Solution change previews are read-only and do not create backups, despite their `PUT` request method.

The order for a successful structural mutation is:

1. Create the pre-change backup.
2. Send the Quickbase mutation.
3. Create the post-change backup.

For multiple applications, all pre-change backups complete before the mutation.
The post-change backups follow a successful response.

If the pre-change backup fails, the mutation is not sent. If the mutation fails, the
post-change backup is not created. If the post-change backup fails, the mutation has already
succeeded and the client raises `QuickbaseBackupError`.

## Disable Backups

Disable backups when performing read-only work, initial exploration, or externally managed
backup workflows:

```python
client = QuickBaseStructureClient(auth, auto_backup=False)
```

This is an explicit safety tradeoff. Mutations proceed without package-managed snapshots.

## Schema Backup

Schema backup exports a configured Quickbase Solution as QBL before and after each mutation:

```python
client = QuickBaseStructureClient(
    auth,
    auto_backup=True,
    backup_method="schema",
    backup_solution_id="solution-id",
    backup_dir="backups",
    backup_fallback_to_clone=False,
)
```

Files are written as:

```text
backups/<app-id>_pre_<UTC timestamp>_<random suffix>.qbl
backups/<app-id>_post_<UTC timestamp>_<random suffix>.qbl
```

The UTC timestamp uses `YYYYmmdd_HHMMSS`.
The random suffix contains 16 lowercase hexadecimal characters.
Each pre-change and post-change pair shares the same timestamp and suffix.
Exclusive file writes never overwrite an existing backup.
If a filename collision occurs, the backup fails or uses the configured pre-change clone fallback.

The configured `backup_solution_id` determines what the exported QBL contains. The client does
not dynamically create or modify that Solution to match each `app_id`. Confirm that the
Solution represents the application structure you intend to protect.

`SolutionsManager.update_solution` automatically uses the target Solution for its schema backups.
For other direct requests, `solution_id_for_backup` can override the global Solution ID.
The backup state captures the selected ID before the mutation.
Later changes to client configuration do not redirect the post-change export.

When no Solution ID is available and clone fallback is disabled, the pre-backup raises
`QuickbaseValidationError`.

## Clone Backup

Clone backup copies the source application before and after a mutation:

```python
client = QuickBaseStructureClient(
    auth,
    auto_backup=True,
    backup_method="clone",
)
```

The clone names are:

```text
Backup_Pre_<app-id>_<UTC timestamp>_<random suffix>
Backup_Post_<app-id>_<UTC timestamp>_<random suffix>
```

Each pair shares the timestamp and random suffix described for schema backups.

Clone backups use:

- `exclude_files=True`
- `keep_data=False`

The source app's users and roles use the normal app-copy default, which is currently enabled.
The current user token is not explicitly assigned to backup clones.

Backup clone requests execute inside `suppress_auto_backup()` so they do not recursively create
more backups.

## Schema-To-Clone Fallback

Schema backup defaults to clone fallback:

```python
client = QuickBaseStructureClient(
    auth,
    auto_backup=True,
    backup_method="schema",
    backup_solution_id=None,
    backup_fallback_to_clone=True,
)
```

Fallback occurs when:

- No global or request-specific Solution ID is available.
- The pre-change QBL export or local pre-backup write fails.

After fallback, both pre-change and post-change backups use app clones for that mutation.

Post-change schema export failures do not fall back to cloning. They raise
`QuickbaseBackupError` after the mutation has already succeeded.

## Parent Application Context

Wrappers created through an app or table retain the application ID:

```python
app = client.app("b12345678")
table = app.table("b23456789")
field = table.field(7)
relationship = table.relationship(3)
```

This context lets field and relationship mutations participate in backups.

The following direct reference omits the application ID:

```python
table = client.table("b23456789")
field = table.field(7)
```

When `auto_backup=True`, `field.update(...)`, `field.delete()`, and equivalent relationship
mutations raise `QuickbaseValidationError` because the backup target is unknown. Supply
`app_id` when creating the table reference:

```python
table = client.table("b23456789", app_id="b12345678")
```

## Temporary Suppression

The client exposes a reentrant context manager:

```python
with client.suppress_auto_backup():
    response = client.request(
        method="POST",
        endpoint="/custom/endpoint",
        payload={"example": True},
        app_id_for_backup="b12345678",
    )
```

Use suppression only when a higher-level workflow already provides equivalent protection.

## Operational Guidance

Before enabling backups in production:

1. Test the chosen strategy against a non-production application.
2. Confirm the user token can export the Solution or copy the app.
3. Confirm `backup_dir` is writable and excluded from source control.
4. Confirm clone naming, retention, and tenant limits with the Quickbase administrator.
5. Decide how to recover when a post-backup fails after the mutation succeeds.

The package creates snapshots but does not implement retention, cleanup, restore, or backup
verification.
