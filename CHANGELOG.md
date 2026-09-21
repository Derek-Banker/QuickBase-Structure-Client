# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-09-21

### Added

- Add table-wide field usage queries with pagination and usage queries for individual fields.
- Add XML methods to change table key fields and field properties, including `doesdatacopy`
  and `allowHTML`, with automatic backups and sanitized error handling.
- Add Solution updates from complete QBL documents, with backups for each supplied application.
  Document the QBL workflow for default table sorting and field choice sources.
- Add read-only QBL change previews before Solution updates.
- Add opt-in live tests for field and table operations with explicit targets and automatic cleanup.
- Add `options=` for field request bodies. Existing positional calls and the `properties=`
  keyword remain compatible. Quickbase's nested `properties` object remains unchanged.

### Fixed

- Remove the field `description` alias from requests when `fieldHelp` is also present.
  The explicit `fieldHelp` value takes precedence.
- Use the target Solution for schema backups of QBL updates, regardless of the global backup target.
- Preserve backup timestamps and append random suffixes to schema filenames and clone names.
  Exclusive file writes prevent existing schema backups from being overwritten.

### Security

- Reject invalid field IDs, table IDs, backup application IDs, and field creation input
  before backups or requests.
- Reject invalid characters in user tokens before HTTP requests and keep token values out of errors.

## [0.1.6] - 2026-06-15

### Added

- Include field choices, query-like field properties, raw field properties, and relationship
  summary fields in compiled schema JSON and Markdown exports.

## [0.1.5] - 2026-06-11

### Added

- Add `QuickbasePermissionError` for HTTP 403 responses while retaining compatibility with
  `QuickbaseAuthError` handlers.
- Add structured `context` and `cause` attributes to package exceptions.
- Add project, repository, and issue tracker URLs to package metadata.

### Changed

- Give schema lookup failures resource-specific summaries for permission, authentication,
  rate-limit, not-found, HTTP, and transport errors.

### Fixed

- Remove schema request pacing introduced in 0.1.4 after diagnostics identified permission
  denial, rather than request rate, as the large-app export failure.
- Populate the documented `cause` attribute on terminal HTTP exceptions.
- Include the changelog, documentation, and examples in source distributions.

## [0.1.4] - 2026-06-10

### Fixed

- Include the underlying request failure in schema compilation errors, including permission
  denials from field and relationship endpoints.

## [0.1.3] - 2026-06-09

### Added

- Add complete user and developer documentation for setup, the public API, request behavior,
  automatic backups, schema and QBL workflows, repository examples, and local development.
- Add single-table schema compilation through `SchemaExporter.compile_schema(..., table_id=...)`
  and the schema export example's `--table-id` option.

## [0.1.2] - 2026-06-08

### Added

- Add repository-specific agent guidance for implementation, testing, safety, documentation,
  changelog maintenance, and releases.
- Add a `docs/` entry point for long-form project documentation.

### Changed

- Enforce Google-style Python docstrings and include example scripts in CI lint and type checks.
- Ignore default schema export and automatic backup output directories.

### Fixed

- Align package metadata with the repository's Unlicense license file.
- Reject empty normalized Quickbase credentials before requests and redact the configured user
  token if an HTTP error response echoes it.
