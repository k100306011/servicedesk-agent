# KB-002: Password reset and multi-factor authentication

- Owner: Identity and Access Management
- Last reviewed: 2026-08-20
- Status: Active
- Applies to: Company-managed identities

Direct the user to the self-service password reset portal. Service desk staff
and automated agents must never ask for or store a password. If self-service
reset fails, create an `Identity` ticket with the error and affected username,
but do not include authentication secrets.

Users enroll a company-approved authenticator through the identity portal.
Never request, repeat, log, or validate an MFA code in chat or in a ticket.
Lost or replaced devices require identity verification by a human service desk
agent before MFA methods are reset.

Repeated unexpected MFA prompts or a reset request the user did not initiate
must be treated as a potential security incident and routed to Security.
