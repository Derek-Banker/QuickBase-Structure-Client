# Implementation Plan - QuickBase-Structure-Client

`QuickBase-Structure-Client` is a Python client focused on managing Quickbase **application structure, schema, roles, and lifecycles**. It mimics the design pattern, exception hierarchy, and transport layer of `QuickBase-Data-Client` to provide a unified experience for developers.

---

## Approved Design Decisions

- **Default Backup Method:** Primary backup defaults to QBL Schema Export (Solutions API). App Cloning (`POST /v1/apps/{appId}/clone`) is supported as an optional flag or fallback if the Solutions API is inaccessible (e.g., non-Enterprise accounts).
- **Auto-Backup Behavior:** Enabled by default. Any mutating structural action (e.g., creating a field, deleting a table, modifying a formula) triggers a backup automatically. This can be globally disabled by initializing the client with `auto_backup=False` (e.g., `QuickBaseStructureClient(auth, auto_backup=False)`).
- **Sync/Async Roadmap:** Focus first on building a robust, fully-featured sync client, keeping class definitions and module separation clean so async wrappers can easily be added later.
- **Schema Exporter Formats:** Exporter supports both a hierarchical, human/LLM-readable Markdown outline and a structured compact JSON representation.

---

## Proposed Architecture & Directory Structure

We will initialize the workspace with the following package layout, mirroring `QuickBase-Data-Client`:

```
QuickBase-Structure-Client/
├── pyproject.toml
├── README.md
├── LICENSE
├── src/
│   └── quickbase_structure_client/
│       ├── __init__.py
│       ├── config.py
│       ├── exceptions.py
│       ├── quickbase_api.py      # Core client (Auth, RequestConfig, Transport)
│       ├── app.py                # App structural edits & trustee management
│       ├── table.py              # Table structural edits
│       ├── field.py              # Field structural edits (formulas, types)
│       ├── relationship.py       # Relationship management
│       ├── trustees.py           # User roles, trustee access edits
│       ├── solutions.py          # Solutions API / QBL / Backup workflows
│       ├── schema_exporter.py    # Human/LLM readable schema generator
│       └── tools/
│           └── backup_manager.py # Backup before/after change interceptors
└── tests/
    ├── conftest.py
    ├── test_client.py
    ├── test_app.py
    ├── test_table.py
    ├── test_field.py
    ├── test_backup.py
    └── test_schema_exporter.py
```

---

## Proposed Changes

### 1. Project Setup

#### [NEW] [pyproject.toml](file:///c:/CFS%20-%20Derek/Programming/Python/QuickBase-Structure-Client/pyproject.toml)
Defines project metadata, dependencies (`requests`, `pandas`, `numpy`), and developer environments (`pytest`, `ruff`, `mypy`).

---

### 2. Core API Client (`quickbase_api.py`, `exceptions.py`, `config.py`)

#### [NEW] [quickbase_api.py](file:///c:/CFS%20-%20Derek/Programming/Python/QuickBase-Structure-Client/src/quickbase_structure_client/quickbase_api.py)
* Exposes `Auth`, `RequestConfig`, and the primary client class `QuickBaseStructureClient`.
* Manages requests, retries with backoff/jitter, custom headers, and `auto_backup` configuration status.

#### [NEW] [exceptions.py](file:///c:/CFS%20-%20Derek/Programming/Python/QuickBase-Structure-Client/src/quickbase_structure_client/exceptions.py)
* Maps Quickbase-specific error responses to clear exception types (`QuickbaseAuthError`, `QuickbaseValidationError`, `QuickbaseHTTPError`, `QuickbaseBackupError`).

---

### 3. Structural Domain Classes

#### [NEW] [app.py](file:///c:/CFS%20-%20Derek/Programming/Python/QuickBase-Structure-Client/src/quickbase_structure_client/app.py)
* Exposes `StructureApp` reference class and handles App structural endpoints:
  - `create_app(name, description, ...)`
  - `update_app(app_id, name, description, ...)`
  - `delete_app(app_id)`
  - `copy_app(app_id, target_name, exclude_files, keep_data, ...)`

#### [NEW] [table.py](file:///c:/CFS%20-%20Derek/Programming/Python/QuickBase-Structure-Client/src/quickbase_structure_client/table.py)
* Exposes `StructureTable` reference class and handles Table structural endpoints:
  - `create_table(app_id, name, plural_name, description, ...)`
  - `update_table(table_id, name, plural_name, ...)`
  - `delete_table(table_id, app_id)`

#### [NEW] [field.py](file:///c:/CFS%20-%20Derek/Programming/Python/QuickBase-Structure-Client/src/quickbase_structure_client/field.py)
* Handles Field/Formula settings:
  - `create_field(table_id, label, field_type, properties)`
  - `update_field(table_id, field_id, properties)` (e.g., setting formulas)
  - `delete_fields(table_id, field_ids)`

#### [NEW] [relationship.py](file:///c:/CFS%20-%20Derek/Programming/Python/QuickBase-Structure-Client/src/quickbase_structure_client/relationship.py)
* Handles table-to-table relationships: `create_relationship`, `update_relationship`, `delete_relationship`.

#### [NEW] [trustees.py](file:///c:/CFS%20-%20Derek/Programming/Python/QuickBase-Structure-Client/src/quickbase_structure_client/trustees.py)
* Manages user access, roles, and trustee memberships:
  - `get_trustees(app_id)`
  - `add_trustees(app_id, trustees_list)`
  - `update_trustees(app_id, trustees_list)`
  - `remove_trustees(app_id, trustees_list)`

---

### 4. Backup & Change Tracking

#### [NEW] [solutions.py](file:///c:/CFS%20-%20Derek/Programming/Python/QuickBase-Structure-Client/src/quickbase_structure_client/solutions.py)
* Handles Solutions API interactions:
  - `export_solution(solution_id)`
  - `export_solution_to_record(solution_id, target_table_id, field_id, record_id)`
  - `create_solution(name, apps)`
  - Local QBL text file exporter.

#### [NEW] [backup_manager.py](file:///c:/CFS%20-%20Derek/Programming/Python/QuickBase-Structure-Client/src/quickbase_structure_client/tools/backup_manager.py)
* Manages the backup interceptor:
  - Automatically executes a QBL backup or App Clone before any mutating structural calls.
  - Takes a post-change snapshot after mutating calls complete.
  - Exposes config options to toggle method-level fallback to cloning if QBL Solutions are restricted.

---

### 5. Human/LLM Schema Exporter

#### [NEW] [schema_exporter.py](file:///c:/CFS%20-%20Derek/Programming/Python/QuickBase-Structure-Client/src/quickbase_structure_client/schema_exporter.py)
* Exporter that retrieves app structures (tables, fields, formulas, properties, relationships).
* Serializes schemas to:
  - **Markdown Exporter:** Hierarchical outline featuring field IDs, names, types, and formula definitions.
  - **JSON Exporter:** Clean, compact JSON document mapping tables to fields, types, formulas, and relationship graphs.

---

## Verification Plan

### Automated Tests
* We will establish mock-based tests using `pytest` and `monkeypatch` to simulate Quickbase API responses.
* Specifically check:
  - Payload composition for creating/updating fields and tables.
  - Auto-backup triggers before and after mutating method invocations.
  - Correct formatting of generated Markdown and JSON outputs.
* Run tests with:
  ```bash
  pytest tests/
  ```

### Manual Verification
* Perform a live test against a staging Quickbase realm to verify:
  - Creation/Deletion of a test app, table, and fields.
  - Trustee updates.
  - Backup exports (QBL or App Clones).
  - Generation of the Markdown schema document and verification of its readability.
