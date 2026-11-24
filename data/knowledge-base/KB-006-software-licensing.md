# KB-006: Software installation and license activation

- Owner: Software Asset Management
- Last reviewed: 2026-08-10
- Status: Active
- Applies to: Company-managed endpoints and enterprise applications

Approved software must be installed from the company software portal. If an
approved application is missing, refresh the portal once and capture the
application name, device ID, and displayed error.

For non-standard software, create a `Software` request containing the product,
business reason, manager approval, and requested duration. An automated agent
must not state that software is approved or licensed unless the system of
record confirms it.

For activation failures, capture the product, license-server name, error code,
and number of affected users. Widespread failures may be an infrastructure
incident. Never place license keys in chat, logs, or tickets.
