# Debug loop (a test or command fails)

Fix this failure properly.

1. Reproduce: run the exact failing command and quote the key error lines.
2. Diagnose: read the relevant code and state the root cause in 2 to 3 sentences with file:line evidence. Do not guess.
3. Fix the root cause. Do not weaken, skip or delete tests, do not special-case the test input, do not hardcode expected values.
4. Re-run the failing test, then its module, then the full suite. Report the counts.
5. If the cause is the environment (missing tool, platform issue), record it in docs/KNOWN_LIMITATIONS.md and make the app degrade gracefully instead.

After three failed fix attempts, stop and summarize what you learned instead of continuing.
