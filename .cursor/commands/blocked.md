# Blocked by a missing tool, dependency or credential

Something is unavailable. Do not simulate it.

1. State exactly what is missing and what you tried, with commands and outputs.
2. Make the affected feature return a clear 503 or "Unavailable: <reason>" in the API, in /api/health and in the UI.
3. Add an entry to docs/KNOWN_LIMITATIONS.md with the install route for this platform.
4. Continue with independent work.
5. Tell me, in numbered steps, what I need to do to unblock it.
