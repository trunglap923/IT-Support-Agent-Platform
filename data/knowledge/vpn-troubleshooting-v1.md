# Demo VPN troubleshooting

## Certificate warning

On Ubuntu, first confirm that the system clock is synchronized. Disconnect the client,
refresh the managed certificate package, and reconnect once. Do not disable certificate
verification.

## Connection timeout

Check the simulated VPN service status before changing local settings. Retry once from a
different network only when the service is operational.

## Evidence for escalation

Record the client version, operating system, timestamp, and the exact safe error code. Do
not attach private keys, passwords, or full configuration exports.
