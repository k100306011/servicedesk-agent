# KB-001: Account and application access

- Owner: Identity and Access Management
- Last reviewed: 2026-08-15
- Status: Active
- Applies to: Microsoft 365, SharePoint, Google Workspace, SaaS applications

## Standard checks

Confirm the user can sign in to the company identity portal, identify the
application and requested role, check existing group membership, and ask the
user to sign out and back in after approved access is granted.

New access requires the application, requested role, business reason, and
manager approval. The service desk may fulfill pre-approved standard roles.
Privileged, administrative, finance, and production access must be routed to
the application owner and must not be granted automatically.

Create an `Access` ticket when approval or an owner decision is required. Use
high priority only when an existing access failure blocks a documented
business-critical activity; a new access request is normally medium priority.
