# AGENTS.md

## Scope

These instructions apply to the entire repository.

## Working Approach

- Inspect the relevant implementation and tests before changing behavior.
- Be skeptical of assumptions about Quickbase payloads and endpoints. Verify them against
  existing tests or authoritative API documentation.
- Ask a concise question when requirements are materially ambiguous or a live/destructive
  operation may be involved. Otherwise, make the smallest reasonable change and proceed.
- Be direct about unsupported behavior, unverified API assumptions, and test gaps.
- Keep changes focused. Do not mix feature work with unrelated cleanup.

## Project Overview

This repository contains a synchronous Python 3.10+ client for Quickbase structural
administration. It covers apps, tables, fields, relationships, trustees, Solutions/QBL,
schema exports, request retries/logging, and automatic schema or clone backups.

The package uses a `src` layout:

- `src/quickbase_structure_client/quickbase_api.py`: authentication, request configuration,
  retries, redacted logging, HTTP error mapping, and top-level client factories.
- `src/quickbase_structure_client/app.py`: application operations and table/trustee helpers.
- `src/quickbase_structure_client/table.py`: table, field, and relationship operations.
- `src/quickbase_structure_client/field.py`: bound field operations.
- `src/quickbase_structure_client/relationship.py`: bound relationship operations.
- `src/quickbase_structure_client/trustees.py`: trustee validation and requests.
- `src/quickbase_structure_client/solutions.py`: Solutions/QBL operations.
- `src/quickbase_structure_client/schema_exporter.py`: schema compilation plus JSON and
  Markdown rendering.
- `src/quickbase_structure_client/tools/backup_manager.py`: pre-change and post-change
  schema/clone backups.
- `src/quickbase_structure_client/exceptions.py`: package exception hierarchy and contextual
  error formatting.
- `tests/`: mock-based unit tests. They are the primary behavioral specification.
- `examples/`: schema export and PTO demo entry points.
- `docs/`: long-form user and developer documentation.

## Environment

Use the repository virtual environment when it exists.

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Do not commit `.env`, credentials, user tokens, generated backups, schema exports, build
artifacts, or cache directories.

## Validation

Match CI before considering a change complete:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -m "not integration"
.\.venv\Scripts\python.exe -m ruff check src tests examples
.\.venv\Scripts\python.exe -m mypy src tests examples
.\.venv\Scripts\python.exe -m pytest tests --cov=quickbase_structure_client --cov-report=term-missing -m "not integration"
```

Run the narrowest relevant test file while iterating, then run the full commands above.
CI and local quality checks include `examples/` so demo entry points cannot bypass linting or
type checking.

The configured branch coverage floor is 70%. Do not lower it to make a change pass.
If a restricted Windows environment cannot access the default pytest temp directory, append
`--basetemp build/pytest-temp` to the pytest command.

## Live Quickbase Safety

- Unit tests must remain isolated from the network and use fakes, monkeypatching, or a
  supplied `requests.Session`.
- Do not run live Quickbase operations unless the user explicitly requests them and confirms
  the target realm/application.
- Treat app deletion, table deletion, field deletion, relationship deletion, trustee changes,
  app copying, and auto-backup clone fallback as potentially destructive or billable actions.
- Never print, log, commit, or include a Quickbase user token in an exception.
- Keep demos dry-run by default. Placeholder credentials must never be accepted for execution.
- Integration tests must retain the `integration` marker and an explicit environment-variable
  gate so normal test runs cannot contact Quickbase.

## Implementation Conventions

- Preserve the synchronous `requests`-based API unless a task explicitly changes that public
  contract.
- Keep all HTTP transport behavior centralized in
  `QuickBaseStructureClient.request(...)`. Resource wrappers should compose endpoints and
  payloads, then delegate to that method.
- API endpoints passed to `request` begin with `/`. Use the existing uppercase HTTP method
  literals.
- Pass dictionaries/lists as JSON payloads. QBL text is a raw string payload and must continue
  to be sent through `data=`, not JSON encoding.
- Use bound wrappers (`StructureApp`, `StructureTable`, `StructureField`, and
  `StructureRelationship`) for resource-specific behavior. Preserve parent IDs when creating
  child wrappers.
- Structural mutations with an application context must pass `app_id_for_backup`. Read-only
  operations must not trigger backups.
- Preserve pre-change and post-change backup ordering. Backup clone operations must remain
  inside `suppress_auto_backup()` to prevent recursive cloning.
- Validate caller input before issuing a request. Raise the most specific package exception,
  normally `QuickbaseValidationError` for invalid arguments.
- Build contextual errors with `format_error_message(...)`. When wrapping another exception,
  preserve it with `raise ... from exc`.
- Map terminal HTTP failures through the existing exception hierarchy. Do not leak raw
  `requests` exceptions as the package API.
- Request/response hooks and debug logging must remain sanitized. Authorization, cookies, API
  keys, tokens, and raw sensitive payload contents must not be exposed.
- Preserve documented Quickbase payload shapes. In particular:
  - Field convenience property `description` maps to Quickbase `fieldHelp`.
  - Field deletion uses the documented field IDs object.
  - App deletion requires the application name confirmation payload.
  - App copy options belong in the existing nested copy-properties payload.
- Schema export must fail with `QuickbaseSchemaError` rather than silently returning a partial
  schema.

## Python Style

- Follow the existing type-annotated style and keep compatibility with Python 3.10.
- Use `from __future__ import annotations` in new Python modules.
- Keep lines at or below 100 characters.
- Ruff rules `D`, `E`, `F`, and `I` are enforced with the Google docstring convention.
- Prefer explicit package exceptions and typed return values over broad `Any`, but use the
  existing `Dict[str, Any]` payload style when matching neighboring API code.
- Avoid broad `except Exception` unless translating an external failure at a deliberate package
  boundary, such as backup orchestration or logging hooks.
- Do not add asynchronous APIs, new runtime dependencies, or abstraction layers without a
  concrete requirement.

## Documentation

### Python Docstrings

- Follow the
  [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
  for Python docstrings. This requirement applies to documentation style, not Google's
  80-character code limit; this repository's configured line length remains 100 characters.
- Use triple double quotes. Start with a one-line summary that ends with punctuation and stays
  within 80 characters. Add a blank line before longer details or section headings.
- Add module docstrings to non-test modules. Add docstrings to public classes, methods, and
  functions, plus internal helpers whose contract or side effects are not obvious.
- Use Google-style `Args:`, `Returns:`, `Yields:`, `Raises:`, and `Attributes:` sections where
  applicable. Do not repeat type information already expressed by annotations.
- Document behavior, units, accepted formats, side effects, mutation, external I/O, and
  exceptions callers are expected to handle. Do not narrate the implementation.
- Keep docstrings synchronized with signatures and behavior in the same change.

### Documentation Files

- Put long-form user guides, API explanations, architecture notes, and development guides under
  `docs/`. Add new pages to `docs/index.md`.
- Keep only repository entry-point and process files at the root: `README.md`, `CHANGELOG.md`,
  `AGENTS.md`, `LICENSE`, and required packaging/configuration files.
- Keep the root `README.md` concise. It should describe the package, provide a working
  quickstart, and link to detailed material in `docs/`.
- Every feature addition, behavior change, deprecation, or removal must update the relevant
  documentation in the same change. Update examples when the public API or recommended workflow
  changes.
- Bug fixes must update documentation when they correct documented behavior or expose a
  user-relevant limitation, migration step, or operational concern.
- Do not add speculative documentation for unsupported behavior. Remove or rewrite stale
  documentation when behavior is removed or changed.
- Check new and modified Markdown for valid headings, fenced code languages, working links, and
  commands that match the supported PowerShell or Python workflow.

### Changelog

- Maintain root `CHANGELOG.md` according to
  [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and Semantic Versioning.
- Every change set must evaluate whether a changelog entry is required. Add every notable
  user-facing or developer-facing change under `Unreleased`; do not dump commit messages or list
  trivial formatting, test-only, or internal refactoring work with no observable effect.
- Group entries under the standard headings: `Added`, `Changed`, `Deprecated`, `Removed`,
  `Fixed`, and `Security`. Omit empty headings.
- Write entries as concise descriptions of user-visible outcomes. Call out breaking changes,
  required migrations, deprecations, and security impact explicitly.
- Keep releases in reverse chronological order. Use headings in the form
  `## [X.Y.Z] - YYYY-MM-DD`, with ISO 8601 dates and comparison links when release tags exist.
- At release time, move applicable `Unreleased` entries into the new version, add a fresh
  `Unreleased` section, and ensure the release notes, package version, and documentation agree.
- Mark withdrawn releases with `[YANKED]` and retain their history.

## Tests

- Add or update tests for every behavior change.
- Follow the existing `test_<behavior>` function style.
- Use `RecordingClient` and `FakeResponse` from `tests/conftest.py` for wrapper payload and
  request-composition tests.
- Assert method, endpoint, payload, headers, and `app_id_for_backup` when changing API calls.
- For retry tests, monkeypatch sleeps/randomness so the suite stays fast and deterministic.
- For filesystem behavior, use pytest's `tmp_path`; do not write generated files into the
  repository.
- Test both successful behavior and the relevant validation/error path.
- Do not weaken assertions merely to accommodate an implementation change.

## Public API And Packaging

- The public package surface is defined in `src/quickbase_structure_client/__init__.py`.
  Deliberately export new public types there and update `__all__`.
- Keep the package version in `pyproject.toml`, `quickbase_api.DEFAULT_USER_AGENT`, and
  `__init__.__version__` synchronized when performing a release version change.
- Keep README examples aligned with the public API when signatures or defaults change.
- Build releases with:

```powershell
.\.venv\Scripts\python.exe -m build --sdist --wheel
```

- Do not edit generated contents under `build/`, `dist/`, or `*.egg-info/`.


## This Document

This document is a living document and meant to change. If asked to apply something to 
the repo or directory as a whole, consider adding that policy to this document. Explicit 
confirmation is required before any changes are made to this document to prevent unintended 
changes.