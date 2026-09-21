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

The realm and token must be nonempty after normalization.
The normalized user token must contain visible ASCII characters without internal whitespace.
Control characters and non-ASCII characters raise `QuickbaseConfigurationError` before a request.

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
    app_ids_for_backup: list[str] | None = None,
    solution_id_for_backup: str | None = None,
    xml_action: str | None = None,
    app_token: str | None = None,
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
table.set_key_field(
    field_id: int | str,
    *,
    app_token: str | None = None,
) -> dict[str, str]
```

Field operations:

```python
table.field(id: int | str, label: str | None = None) -> StructureField
table.create_field(
    label: str,
    field_type: str,
    options: dict[str, Any] | None = None,
    *,
    properties: dict[str, Any] | None = None,
) -> dict[str, Any]
table.list_fields(
    include_field_perms: bool = False,
) -> list[dict[str, Any]]
table.update_field(
    field_id: int | str,
    options: dict[str, Any] | None = None,
    *,
    properties: dict[str, Any] | None = None,
) -> dict[str, Any]
table.get_fields_usage(
    skip: int | None = None,
    top: int | None = None,
) -> list[dict[str, Any]]
table.update_field_xml(
    field_id: int | str,
    options: dict[str, Any],
    *,
    app_token: str | None = None,
) -> dict[str, str]
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
Table operations validate table IDs before requests and application IDs before mutations.
These IDs must contain only ASCII letters and digits. Validation does not prove that a resource exists.

`get_fields_usage` returns one page of usage data. `skip` must be a nonnegative integer.
`top` must be a positive integer. Boolean values are invalid for either argument.
The method does not fetch additional pages or trigger backups.

`set_key_field` calls Quickbase's XML
[`API_SetKeyField`](https://help.quickbase.com/docs/api-setkeyfield).
The selected field must support unique values. Existing values must be unique and nonblank.
Quickbase checks field eligibility and administrator permissions.

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
    options: dict[str, Any] | None = None,
    *,
    properties: dict[str, Any] | None = None,
) -> dict[str, Any]
field.get_details(
    include_field_perms: bool = False,
) -> dict[str, Any]
field.update(
    options: dict[str, Any] | None = None,
    *,
    properties: dict[str, Any] | None = None,
) -> dict[str, Any]
field.get_usage() -> list[dict[str, Any]]
field.update_xml(
    options: dict[str, Any],
    *,
    app_token: str | None = None,
) -> dict[str, str]
field.delete() -> dict[str, Any]
```

`options` contains the whole REST request body for field creation or updates.
Quickbase's type-specific `properties` object remains nested inside that body:

```python
field.update(
    options={
        "required": True,
        "properties": {
            "choices": ["Pending", "Approved"],
            "allowNewChoices": False,
        },
    },
)
```

The legacy `properties=` keyword remains an alias for `options=`. Existing positional calls
also work. Supplying both arguments raises `QuickbaseValidationError`.
The nested REST key `properties` does not change.

`create` and `update` accept `description` as an alias for `fieldHelp`.
If both keys are present, `fieldHelp` wins and the client removes `description`.
The client validates the body and nested `properties` as dictionaries.
Field creation requires nonempty string values for `label` and `fieldType` after option overrides.
Field IDs must be positive integers or strings of ASCII decimal digits.
Boolean and fractional field IDs raise `QuickbaseValidationError` before a request.
Quickbase validates individual REST options and their compatibility with the field type.
`required` and `unique` are update options. The REST creation endpoint does not accept them.
Mutations require `app_id` when automatic backup is enabled. Deletion clears the wrapper's
field ID.

`get_usage` returns Quickbase's list of usage entries for the bound field without backups.
The single-field endpoint also returns a list. Each entry contains `field` and `usage` objects.

### XML Field Updates

`update_xml` calls
[`API_SetFieldProperties`](https://help.quickbase.com/docs/api-setfieldproperties).
Its keys are XML property tags, including their original spelling and capitalization.
The client validates documented tag names, scalar values, lists, and boolean values.
Boolean values become `1` or `0`. `choices` accepts a list of strings.
Empty dictionaries, unsupported tags, and authentication tags raise `QuickbaseValidationError`.

```python
field.update_xml({"doesdatacopy": False})
rich_text_field.update_xml({"allowHTML": True})
```

Quickbase checks field-type applicability and limits for each property. The REST spelling
`doesDataCopy` is not the XML tag `doesdatacopy`.
XML methods accept an optional `app_token` for apps that require one.
They return XML response elements as a dictionary of strings.
The request layer checks the XML `errcode` before it creates a post-change backup.

Existing field type conversion has no supported wrapper. Quickbase documents this operation
as a UI change in its [`API_AddField` guidance](https://help.quickbase.com/docs/api-addfield).
For default table sorting and choice-source references, see
[QBL updates](schema-exports-and-solutions.md#update-a-solution).

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
solutions.update_solution(
    solution_id: str,
    qbl: str,
    *,
    app_ids_for_backup: list[str] | None = None,
    errors_as_success: bool = False,
) -> dict[str, Any]
solutions.preview_solution_changes(
    solution_id: str,
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

`preview_solution_changes` returns proposed changes without applying them or creating backups.
`update_solution` uses its target Solution ID for schema backups, regardless of the client's
global `backup_solution_id`.

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

Compiled fields include extracted formulas, choices, query-like properties, unique/required
flags, and the raw Quickbase field `properties` dictionary. Compiled relationships include
relationship `summaryFields` when Quickbase returns them.

Compilation raises `QuickbaseSchemaError` instead of returning a partial schema when table
field or relationship retrieval fails. The error message includes the underlying HTTP,
transport, or parsing cause.

## Exceptions

All package exceptions derive from `QuickbaseError`.

| Exception | Meaning |
|---|---|
| `QuickbaseValidationError` | Invalid caller input |
| `QuickbaseConfigurationError` | Invalid local client or request configuration |
| `QuickbaseTransportError` | Exhausted network or timeout retries |
| `QuickbaseHTTPError` | Other terminal unsuccessful HTTP response |
| `QuickbaseAuthError` | HTTP 401 authentication failure |
| `QuickbasePermissionError` | HTTP 403 authorization failure |
| `QuickbaseRateLimitError` | HTTP 429 after retries |
| `QuickbaseNotFoundError` | HTTP 404 |
| `QuickbasePayloadError` | Invalid request or response payload content |
| `QuickbaseSchemaError` | Schema lookup or compilation failure |
| `QuickbaseBackupError` | Pre-change or post-change backup failure |

Every package exception exposes a `context: dict[str, Any]` attribute. Wrapper exceptions also
set `cause` when an underlying exception was translated. This allows callers to inspect status
codes and causes without parsing the formatted message.

`QuickbaseValidationError` also derives from `ValueError`.
`QuickbaseConfigurationError` and `QuickbasePayloadError` derive from
`QuickbaseValidationError`. `QuickbaseAuthError` also derives from `PermissionError`.
`QuickbasePermissionError` derives from `QuickbaseAuthError`.
