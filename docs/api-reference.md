# API Reference

This reference summarizes the public imports from `quickbase_structure_client`. Methods return
Quickbase response dictionaries unless another return type is stated.

## Package Version

```python
from quickbase_structure_client import __version__
```

`__version__` contains the installed package version as a string.

## Authentication

### `Auth`

```python
Auth(
    realm: str,
    user_token: str,
    *,
    user_agent: dict[str, str] | None = None,
)
```

Stores normalized realm and token values and builds authenticated headers.

Properties and methods:

| Member | Description |
|---|---|
| `realm` | Bare Quickbase realm hostname |
| `user_token` | Token without the `QB-USER-TOKEN` prefix |
| `user_agent` | Assembled user-agent string; property is writable |
| `headers` | Authenticated request headers |
| `session()` | New `requests.Session` populated with authenticated headers |

Helpers:

```python
normalize_realm_hostname(realm: str) -> str
normalize_user_token(user_token: str) -> str
```

## Request Configuration

### `RequestConfig`

```python
RequestConfig(
    timeout: float | tuple[float, float] = (3.0, 25.0),
    retry_count: int = 2,
    retryable_status_codes: frozenset[int] = frozenset({429, 502, 503, 504}),
    backoff_factor: float = 0.5,
    jitter: float = 0.25,
    respect_retry_after: bool = True,
    request_log_hook: Callable[[dict[str, Any]], None] | None = None,
    response_log_hook: Callable[[dict[str, Any]], None] | None = None,
)
```

See [Request Configuration](request-configuration.md) for retry and logging semantics.

## Client

### `QuickBaseStructureClient`

```python
QuickBaseStructureClient(
    auth: Auth,
    base_url: str = "https://api.quickbase.com/v1",
    *,
    request_config: RequestConfig | None = None,
    session: requests.Session | None = None,
    auto_backup: bool = True,
    backup_method: Literal["schema", "clone"] = "schema",
    backup_solution_id: str | None = None,
    backup_dir: str = "backups",
    backup_fallback_to_clone: bool = True,
)
```

Manager attributes:

| Attribute | Type | Purpose |
|---|---|---|
| `app_manager` | `StructureApp` | Unbound application operation helper |
| `solutions` | `SolutionsManager` | QBL and Solution operations |
| `exporter` | `SchemaExporter` | Compiled schema exports |
| `backup_manager` | `BackupManager` | Internal backup orchestration |
| `trustees` | `TrusteesManager` | Application trustee operations |

Convenience methods:

```python
client.app(id: str, name: str | None = None) -> StructureApp
client.table(
    id: str,
    *,
    app_id: str | None = None,
    name: str | None = None,
) -> StructureTable
client.create_app(
    name: str,
    description: str | None = None,
    *,
    assign_token: bool = False,
) -> StructureApp
client.update_app(
    app_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    variables: list[dict[str, Any]] | None = None,
    properties: dict[str, Any] | None = None,
) -> dict[str, Any]
client.delete_app(app_id: str, *, confirm_name: str) -> None
client.copy_app(
    app_id: str,
    *,
    target_name: str,
    description: str | None = None,
    exclude_files: bool = True,
    keep_data: bool = False,
    users_and_roles: bool = True,
    assign_user_token: bool = False,
) -> StructureApp
```

Low-level methods:

```python
client.request(
    *,
    method: Literal["GET", "POST", "DELETE", "PUT", "PATCH"],
    endpoint: str,
    payload: dict[str, Any] | list[Any] | str | bytes | None = None,
    headers: Mapping[str, str] | None = None,
    app_id_for_backup: str | None = None,
) -> requests.Response

client.suppress_auto_backup() -> ContextManager[None]
```

Use bound wrappers for normal resource operations.

## Applications

### `StructureApp`

Properties:

| Property | Type | Description |
|---|---|---|
| `id` | `str | None` | Resolved application ID |
| `name` | `str | None` | Known application name |

Application operations:

```python
app.get_details() -> dict[str, Any]
app.create(
    name: str,
    description: str | None = None,
    *,
    assign_token: bool = False,
) -> StructureApp
app.update(
    name: str | None = None,
    description: str | None = None,
    variables: list[dict[str, Any]] | None = None,
    properties: dict[str, Any] | None = None,
) -> dict[str, Any]
app.copy(
    target_name: str,
    description: str | None = None,
    exclude_files: bool = True,
    keep_data: bool = False,
    users_and_roles: bool = True,
    assign_user_token: bool = False,
) -> StructureApp
app.delete(confirm_name: str | None = None) -> None
```

Table and role operations:

```python
app.create_table(
    name: str,
    plural_name: str | None = None,
    single_record_name: str | None = None,
    description: str | None = None,
) -> StructureTable
app.list_tables() -> list[dict[str, Any]]
app.table(id: str, name: str | None = None) -> StructureTable
app.get_roles() -> dict[str, Any]
```

Trustee operations:

```python
app.get_trustees() -> dict[str, Any]
app.add_trustees(trustees: list[dict[str, Any]]) -> dict[str, Any]
app.update_trustees(trustees: list[dict[str, Any]]) -> dict[str, Any]
app.remove_trustees(trustees: list[dict[str, Any]]) -> dict[str, Any]
```

Operations requiring an app ID raise `QuickbaseValidationError` on an unresolved wrapper.
Deletion also requires an application name, either stored on the wrapper or passed as
`confirm_name`.

## Tables

### `StructureTable`

Properties:

| Property | Type | Description |
|---|---|---|
| `id` | `str` | Table ID |
| `app_id` | `str | None` | Known parent application ID |
| `name` | `str | None` | Known table name |

Table operations:

```python
table.get_details() -> dict[str, Any]
table.update(
    name: str | None = None,
    plural_name: str | None = None,
    single_record_name: str | None = None,
    description: str | None = None,
) -> dict[str, Any]
table.delete() -> None
```

Field operations:

```python
table.field(id: int | str, label: str | None = None) -> StructureField
table.create_field(
    label: str,
    field_type: str,
    properties: dict[str, Any] | None = None,
) -> dict[str, Any]
table.list_fields(
    include_field_perms: bool = False,
) -> list[dict[str, Any]]
table.update_field(
    field_id: int | str,
    properties: dict[str, Any],
) -> dict[str, Any]
table.delete_fields(
    field_ids: list[int | str],
) -> dict[str, Any]
```

Relationship operations:

```python
table.relationship(id: int | str) -> StructureRelationship
table.list_relationships(skip: int | None = None) -> list[dict[str, Any]]
table.create_relationship(
    payload: dict[str, Any],
) -> dict[str, Any]
table.update_relationship(
    relationship_id: int | str,
    payload: dict[str, Any],
) -> dict[str, Any]
table.delete_relationship(
    relationship_id: int | str,
) -> dict[str, Any]
```

Table mutations require a known `app_id`. Read-only field and relationship listing does not.

## Fields

### `StructureField`

Properties:

| Property | Type | Description |
|---|---|---|
| `table_id` | `str` | Parent table ID |
| `id` | `int | str | None` | Resolved field ID |
| `app_id` | `str | None` | Known parent application ID |
| `label` | `str | None` | Known field label |

Methods:

```python
field.create(
    label: str,
    field_type: str,
    properties: dict[str, Any] | None = None,
) -> dict[str, Any]
field.get_details(
    include_field_perms: bool = False,
) -> dict[str, Any]
field.update(
    properties: dict[str, Any],
) -> dict[str, Any]
field.delete() -> dict[str, Any]
```

`create` and `update` accept `description` as an alias for `fieldHelp`. Mutations require
`app_id` when automatic backup is enabled. Deletion clears the wrapper's field ID.

## Relationships

### `StructureRelationship`

Properties:

| Property | Type | Description |
|---|---|---|
| `child_table_id` | `str` | Child table ID |
| `id` | `int | str | None` | Resolved relationship ID |
| `app_id` | `str | None` | Known parent application ID |

Methods:

```python
relationship.create(payload: dict[str, Any]) -> dict[str, Any]
relationship.update(payload: dict[str, Any]) -> dict[str, Any]
relationship.delete() -> dict[str, Any]
```

Payloads are passed through to Quickbase. The client does not provide a typed relationship
payload model. Mutations require `app_id` when automatic backup is enabled. Deletion clears the
wrapper's relationship ID.

## Trustees

### `TrusteesManager`

```python
manager.get_trustees(app_id: str) -> dict[str, Any]
manager.add_trustees(
    app_id: str,
    trustees: list[dict[str, Any]],
) -> dict[str, Any]
manager.update_trustees(
    app_id: str,
    trustees: list[dict[str, Any]],
) -> dict[str, Any]
manager.remove_trustees(
    app_id: str,
    trustees: list[dict[str, Any]],
) -> dict[str, Any]
```

Add and remove payloads require `id`, `type`, and `roleId`. Update payloads additionally require
`oldRoleId`.

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
```

Trustee mutations are structural changes and participate in automatic backups.

## Solutions

### `SolutionsManager`

```python
solutions.export_solution(
    solution_id: str,
    qbl_version: str | None = None,
) -> str
solutions.create_solution(
    qbl: str,
    *,
    errors_as_success: bool = False,
) -> dict[str, Any]
solutions.export_solution_to_record(
    solution_id: str,
    table_id: str,
    field_id: int | str,
    record_id: int | str | None = None,
    qbl_version: str | None = None,
) -> dict[str, Any]
solutions.export_solution_to_file(
    solution_id: str,
    filepath: str | Path,
    qbl_version: str | None = None,
) -> Path
```

See [Schema Exports and Solutions](schema-exports-and-solutions.md).

## Schema Exporter

### `SchemaExporter`

```python
exporter.compile_schema(
    app_id: str,
    *,
    table_id: str | None = None,
) -> dict[str, Any]
exporter.to_json(
    schema: dict[str, Any],
    filepath: str | Path | None = None,
) -> str
exporter.to_markdown(
    schema: dict[str, Any],
    filepath: str | Path | None = None,
) -> str
```

Supplying `table_id` compiles only that table and returns the normal app-shaped schema with one
entry in `tables`.

Compilation raises `QuickbaseSchemaError` instead of returning a partial schema when table
field or relationship retrieval fails.

## Exceptions

All package exceptions derive from `QuickbaseError`.

| Exception | Meaning |
|---|---|
| `QuickbaseValidationError` | Invalid caller input |
| `QuickbaseConfigurationError` | Invalid local client or request configuration |
| `QuickbaseTransportError` | Exhausted network or timeout retries |
| `QuickbaseHTTPError` | Other terminal unsuccessful HTTP response |
| `QuickbaseAuthError` | HTTP 401 or 403 |
| `QuickbaseRateLimitError` | HTTP 429 after retries |
| `QuickbaseNotFoundError` | HTTP 404 |
| `QuickbasePayloadError` | Invalid request or response payload content |
| `QuickbaseSchemaError` | Schema lookup or compilation failure |
| `QuickbaseBackupError` | Pre-change or post-change backup failure |

`QuickbaseValidationError` also derives from `ValueError`.
`QuickbaseConfigurationError` and `QuickbasePayloadError` derive from
`QuickbaseValidationError`. `QuickbaseAuthError` also derives from `PermissionError`.
