# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] [0.1.4] - 2026-06-10

### Fixed

- Pace schema lookup requests during large exports to avoid Quickbase's general API rate limit,
  and include the underlying request failure in schema compilation errors.

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
