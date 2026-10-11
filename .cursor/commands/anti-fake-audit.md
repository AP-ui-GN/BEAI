# Anti-fake audit (end of every milestone, or whenever a result looks too good)

Audit for fabricated or misleading behaviour. Report first, change nothing yet.

- Search for: hardcoded scientific numbers or sequences in application code, random() or Math.random, timers or sleeps imitating progress, try/except blocks returning default values, mock, fake, dummy, sample or placeholder identifiers, and stubs that return success.
- List every UI control and what it triggers. Flag dead ones.
- For every API route that returns scientific values, trace each value to its source: an input file, a computation, or an external record. Flag any that cannot be traced.
- For every test, state whether its expected value was obtained independently of the code under test.
- Confirm that network failures, missing tools and bad input produce errors and store no records.

Output a table: finding, file:line, severity, proposed fix. Then wait for my go-ahead.
