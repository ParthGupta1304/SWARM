# Groq requests, rotated keys and run failures

The recurring generic BudgetAccountingError was traced to an actor receiving
HTTP 400 with code `tool_use_failed`. Groq could not parse the model's native
tool call. The old code marked usage unknown, cancelled the shared budget and
replaced the useful cause with a generic console error. Changing accounts does
not fix malformed model output.

JSON object mode subsequently produced HTTP 400 `json_validate_failed` on live
runs. Groq validates generated JSON in that mode and can reject malformed output
without returning usage. A successful single-request probe did not cover this
failure on subsequent actor decisions.

Current GPT-OSS requests to Groq use ordinary text completions, prompted to return
one JSON action with the permitted action schemas in the stable system prompt.
Both native tool parameters and `response_format` are omitted; reasoning is
excluded from the returned content. The app parses the complete response as JSON,
rejects truncated responses and validates the action before execution. Invalid
output retains reported token usage and counts toward the existing three-invalid-
decisions limit instead of invoking the provider's JSON validation error path.
The output ceiling is 2,048 tokens for these reasoning-model decisions, admitted
through the existing shared token/dollar budget and provider pacer. The
existing tool allowlist, JSON Schema validation, fixed account identities and
one-action policy still apply before HTTP execution. A syntactically valid JSON
response can still contain invalid arguments, which remain rejected and counted.
Other providers retain their native tool request format. This request-format
change has not been subjected to a new multi-seed discovery benchmark.

Each new run reads the credential from the current local `.env` file rather
than reusing the startup-loaded value in `os.environ`. A named key explicitly
present in that file takes precedence; an empty value is not replaced by the
stale value of the same environment variable. Without a local entry, server
environment variables still work for hosting. An already running client's key
does not change mid-request; stop active work before changing account settings.
Changing the model or provider endpoint still requires reloading the launcher.

The dashboard now preserves safe provider diagnostics:

| Failure | Meaning | Next step |
| --- | --- | --- |
| HTTP 400, tool_use_failed | Native tool formatting failed | Current Groq GPT-OSS text action requests avoid this native parser path. |
| HTTP 400, json_validate_failed | Provider rejected generated JSON | Current text action requests validate JSON locally and omit provider JSON mode. Restart an older launcher to apply the fix. |
| HTTP 400, other | Request/model options rejected | Check model and supported parameters. |
| HTTP 401 | Key rejected | Update the local key, then start a new run. |
| HTTP 403 | Account/model permission denied | Check account restrictions and model access. |
| HTTP 429 | Provider limit or account quota | Wait for reset or check account limits. |
| HTTP 5xx / connection failure | Provider outage or transport failure | Retry a new run after connectivity/service recovers. |
| Missing/inconsistent usage | Exact token accounting unavailable | The run stops safely and is not scored as a completed benchmark. |

Errors contain only an HTTP status, a whitelisted code and fixed explanatory
text. Raw SDK messages, request headers, provider payloads and keys are excluded.
The first shared-budget failure is retained rather than overwritten by later
actors reporting that another request's usage is unknown.

Unknown usage still fails closed: the fix does not invent zero token usage,
ignore caps or retry potentially billed requests without a bound.

Verification: mocked SDK responses cover valid JSON, rejected actions, 400/401/
429 classification, shared-budget cause propagation and local credential
rotation. An ASGI check covers the error reaching the dashboard. Two capped real
Groq decision requests passed (buyer and fraudster schemas), using 1,218 reported
tokens at an estimated $0.00025965. No marketplace actions were executed by
those probes; they are not new discovery/benchmark results.

Follow-up verification for `json_validate_failed`: all 31 focused Python checks
and Ruff checks passed. After restarting the launcher, a real dashboard
`POST /api/start` completed all six rounds: run
`2ed4e97d-d925-4d2f-b8d8-e3673dcad570`, 33 marketplace actions, 43,639 reported
tokens, estimated cost $0.00839415, and no provider error. Six actors reached the
existing invalid-decision limit; the run completed without bypassing validation.
This is a workflow smoke test, not a multi-seed benchmark or discovery acceptance.

Provider references: [Groq JSON mode](https://console.groq.com/docs/structured-outputs),
[error codes](https://console.groq.com/docs/errors), and
[rate limits](https://console.groq.com/docs/rate-limits).
