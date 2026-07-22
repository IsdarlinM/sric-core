# Troubleshooting

Run `sric doctor --json`. For PATH issues, confirm `~/.local/bin` (Linux) or `%LOCALAPPDATA%\SRIC\bin` (Windows) is present in a newly opened shell. SRIC intentionally rejects non-loopback Web/API binding until authenticated TLS mode is implemented.
