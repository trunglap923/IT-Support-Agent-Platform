# Docker troubleshooting

## Cache cleanup

Inspect disk usage before pruning unused build cache. Run the dry-run or listing command
first and preserve named volumes. Deleting all volumes is not an approved troubleshooting
step.

## Pull failures

For an authentication error, refresh the short-lived token. For a certificate error, follow
the managed CA procedure; never add an insecure Registry exception.

## Escalation data

Include the image path, safe error code, Docker version, and Registry request ID. Do not
include the token itself.
