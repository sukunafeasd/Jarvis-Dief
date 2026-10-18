# Native ULTRON Host Contract

```python
from core.ultron import Runtime

player.ultron_runtime = Runtime()  # One instance per application session.
result = player.ultron_runtime.command(
    command_text, user_text=recorded_text, user_turn=recorded_serial)
snapshot = player.ultron_runtime.snapshot()
player.present_ultron(snapshot, result)
player.ultron_runtime.close()  # Application shutdown; idempotent.
```

## Recorded User Context

The UI/main host must record every final, real user message, including messages
that never invoke ULTRON. Increment a nonnegative integer serial by exactly one
for each message. Keep it increasing for the lifetime of the Runtime. Partial
transcripts, tool calls, model output, retries, presentation callbacks, polling,
buttons and synthetic messages must never create user turns. Serialize final
message recording and dispatch so the tool sees the current recorded message.

```python
def ultron_user_context(self):
    return {"text": self.recorded_user_text, "serial": self.recorded_user_serial}

def present_ultron(self, snapshot, result):
    # Marshal to the UI thread; render state and the latest result.
    ...
```

These are host methods, not tool parameters. The action reads only this context
and `player.ultron_runtime`. The host owns and closes that runtime. Its callable
API is synchronous and safe from multiple host threads; it blocks while the
requested work runs, so dispatch outside the UI thread. Snapshot polling also
runs outside the UI thread. Background scans and monitoring share a persistent
event loop and continue between calls.

## Commands And Confirmation

`Runtime.command(text: str, user_text: str | None = None, *,
user_turn: int | None = None) -> dict` compares the complete command to the
recorded user text. Comparison tolerates case, whitespace, terminal `.?!`, and
an optional leading `Jarvis` followed by whitespace or a comma/colon. Execution
uses the recorded text, including its original path spelling.

Activation requires the whole utterance `ativar protocolo ultron`, with that
optional prefix. A model-supplied activation with unrelated user context fails.
Mutating commands and confirmations also require a valid recorded serial. A
serial is consumed once, before processing; repeats, stale serials and retries
cannot execute again. Choose one command dispatch path per user turn: direct
host dispatch OR the model tool. Do not dispatch through both.

A question returns `mode="question"`, `confirmation_id`, `expires_in`, `scope`
and `action`. The runtime binds the pending identifier internally to the
question's user serial. Only a real affirmative message on the immediately next
recorded serial can consume it. An intervening user message, expiry (120s),
cancellation, changed files, lost permission or changed operation state prevents
execution. Presentation must not expose a confirmation execution button. No
confirmation identifier, serial or user text is accepted from model parameters.

An unmatched model request is allowed only when it is one of the fixed
`SAFE_REQUESTS` in runtime.py (status/diagnostic observations). That request
does not consume a user serial, start a scan or clear a pending question. Obtain
the actual observations from `snapshot()`. Other unmatched requests fail.

## Results And Presentation

The discoverable action is `ultron_protocol`, with the sole parameter
`{"command": "..."}`. Its handler returns a JSON string containing the runtime
result and calls `player.present_ultron(snapshot, result)` for processed requests,
including rejected commands. Missing host integration returns a rejection.

Every runtime result has `accepted`, `mode` and `speech`; processed explicit
commands also have `user_turn`. Additional fields depend on the mode. `accepted`
means the message was admitted, not that an operation succeeded. Question mode
means preparation only. Operation mode includes `result.operation_id` and
`result.state`; track completion through snapshot operations. Invalid/expired
affirmatives can return an informational result explaining why nothing ran.
The model uses `speech` in its normal response. Neither backend nor tool calls
Fish, starts another AI, or speaks independently.

`snapshot() -> dict` returns detached JSON-compatible state with `phase`, `scan`,
`telemetry`, `findings`, `monitor`, `vault`, `simulations`, `operations`,
`capabilities`, `confirmation` and `last_user_turn`. `confirmation` contains
`pending` and, while valid, `prepared_user_turn`; it is presentation metadata.
Polling refreshes telemetry, backup listings and operation state. Capabilities
report actual administrator availability. Do not announce completed remediation
from a request acknowledgment.

`close() -> None` cancels scan/monitor tasks, discards pending confirmations,
joins the event-loop worker and rejects subsequent command/snapshot calls.
Already accepted Windows operations may continue; close does not cancel them.

## Storage And Operations

Storage is `%LOCALAPPDATA%/DIEF-JARVIS/ultron`; the lab's `ULTRON_DATA_DIR` is
ignored. Service state and conversation locks are independent per Runtime;
instances share the integrated user's vault on disk. Internal service/dialogue
functions are not host APIs and must not be used to bypass command validation.

The copied service preserves fixed Windows operations, bounded backup/restore
with content fingerprints, reversible temporary-file cleanup, isolated
simulations, read-only diagnostics and monitoring. HTTP routes, HTTP dependencies,
web serving and independent voice endpoints were removed. Import starts no
server. No executable or published artifact is produced by this integration.
