# KB-004: Network drives and shared folders

- Owner: Workplace Infrastructure
- Last reviewed: 2026-08-02
- Status: Active
- Applies to: Managed network drives and shared folders

Confirm the user is connected to the office network or approved VPN. Capture
the share path, exact error, and whether other folders on the same share are
accessible. Do not copy confidential file contents into a ticket.

Reconnect using the published share path and refresh the user's sign-in token.
If only one folder is denied, treat it as an access issue rather than remapping
the whole drive. Do not change permissions without data-owner approval.

Create a `Network` ticket for connectivity or mapping failures. Create an
`Access` ticket for folder-level permission requests and identify the data
owner when known.
