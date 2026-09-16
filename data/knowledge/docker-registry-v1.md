# Demo Docker Registry

## Authentication

Use a short-lived access token instead of the account password. Pass the token through
standard input to the Docker client and do not save it in shell history or source code.

## Certificate setup

Use only the CA bundle distributed by the demo IT portal. Restart the Docker daemon after
installing the bundle, then retry the login once.

## Safe diagnostics

Capture the HTTP status and the Registry request ID. Redact authorization headers before
adding logs to a support ticket.
