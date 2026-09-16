# IT escalation guide

## VPN

Escalate after checking service status and retrying once. Include the safe error code,
operating system, client version, and timestamp.

## Docker Registry

Escalate certificate failures only after applying the managed CA bundle and restarting the
daemon. Authentication failures require a refreshed short-lived token first.

## GitLab

Access requests require project, requested role, business reason, and manager confirmation.
Security incidents bypass normal troubleshooting and go directly to the IT security queue.
