# KB-009: Backup verification and restore requests

- Owner: Data Protection
- Last reviewed: 2026-07-12
- Status: Active
- Applies to: Managed endpoint, file-share, and application backups

Identify the system, backup policy, affected data, approximate last-known-good
time, and business impact. A successful job status confirms that a backup ran;
it does not by itself prove every file can be restored.

Create a `DataProtection` ticket with restore scope, target location, requested
restore point, data owner, and approval when required. Restore into an
alternate location when possible to avoid overwriting current data.

Do not claim a restore succeeded until the restore system reports completion
and the requester or data owner verifies the result.
