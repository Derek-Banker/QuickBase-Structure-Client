# Project Documentation

Long-form user and developer documentation for QuickBase Structure Client belongs in this
directory. Keep this index current whenever documentation pages are added, renamed, or removed.

## User Guides

- [Getting Started](getting-started.md): installation, credentials, wrappers, mutations, and
  error handling.
- [API Reference](api-reference.md): public classes, methods, signatures, and exceptions.
- [Request Configuration](request-configuration.md): timeouts, retries, logging hooks, sessions,
  and direct requests.
- [Automatic Backups](automatic-backups.md): schema backups, clone backups, fallback behavior,
  and operational cautions.
- [Schema Exports and Solutions](schema-exports-and-solutions.md): compiled JSON/Markdown
  schemas and raw QBL workflows.
- [Examples](examples.md): schema export command and PTO demo configuration.

## Project Guides

- [Development](development.md): local setup, repository structure, validation, testing, and
  release builds.
- [Project overview](../README.md): package summary and short quickstart.
- [Changelog](../CHANGELOG.md): notable released and unreleased changes.

## Documentation Expectations

Feature additions, behavior changes, deprecations, and removals must update the relevant
documentation in the same change. Keep the root README focused on package discovery and initial
use; put detailed guides and reference material in this directory.
