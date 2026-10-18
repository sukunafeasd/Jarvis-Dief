# FORJA Parent Contract

Only this package and its tests are part of the backend delivery. It imports no
Qt, UI, voice, settings or spatial modules. Call the synchronous facade from a
parent worker, and poll `snapshot()` from any thread. Do not create a second
runtime for settings: use the same instance (`window._forge_runtime` or
`ui.forge_runtime`). Polling snapshots never starts Codex or makes API calls.

```python
from core.forge import Runtime

runtime = Runtime(export_roots=[host_selected_export_root])
runtime.connect()  # isolated handshake + account status; no model generation
runtime.connect(auth_mode='apiKey', key=user_key, model='')
runtime.connect(auth_mode='chatgpt')  # result['auth_url']: open official login
runtime.command('create', prompt='Build a planet', name='Planet')
runtime.command('steer', prompt='Reduce rings by 30%')
runtime.command('cancel')
runtime.command('save', entrypoint='index.html')
runtime.command('save_library', name='Experimental reactor')
runtime.command('export', destination=absolute_new_directory)
runtime.command('undo')
runtime.command('list')
runtime.command('open', project_id=known_project_id)
state = runtime.snapshot()
runtime.close()  # application shutdown, not merely leaving the FORJA screen
```

`new` aliases `create`; `continue` aliases `steer`. `command()` returns a dict
with `accepted`, optional `error`, and command-specific fields. Create/steer
return once the server accepts input, not at turn completion. Delivery timeouts
are ambiguous: inspect state before retrying. Never automatically resend an
ambiguous steer. Only an explicit inactive/mismatched-turn RPC rejection permits
a continuation, on the same project/thread. `approve` fails closed: no approval
is automatically accepted. There is no fictional pause API.

Snapshot is a detached JSON-compatible dict:

- `phase`: `idle`, `running`, `ready`, `error` (no pretend confirmations).
- `project`: `id`, `name`, `revision`, `thread_id`, `state`, `entrypoint`, `validation`.
- `activities`: bounded real items, commands, file changes, public messages and completion.
- `preview_url`: last renderer-validated stable revision, or null.
- `candidate_preview_url`, `candidate_revision`: integrity-checked HTML candidate.
- `projects`: persistent project summaries; `request`: null (escalations denied).
- `serial`: monotonically increasing change counter; `error`: actionable failure.
- `transport`, `connection`, `authenticated`, `generation_verified`, `sandbox`.

Authentication is distinct from successful generation. A successful login does
not prove access to a particular model. `models` comes from `model/list` after
authentication; no invented default model. `generation_verified` only describes
an actually completed turn, not render validation or correctness of its tests.

## Preview Integration

Load candidates in an isolated WebEngine profile **without any QWebChannel or
native bridge**. Do not load generated HTML into the existing privileged spatial
page. Host must validate a candidate and then call:

```python
runtime.command('validate_preview', project_id=state['project']['id'],
    revision=state['candidate_revision'], candidate_url=state['candidate_preview_url'], evidence={
    'syntax': True, 'assets': True, 'initialized': True,
    'nonblank': True, 'framing': True, 'console_errors': [],
})
```

The host must obtain these facts from its actual renderer/checks. This backend
does not fabricate browser evidence. Stale or failed validation keeps the last
stable preview. The server exposes only allowlisted revision assets, checks
their stored hashes on every request, denies traversal, symlinks, junctions,
hard links, directory listing, invalid Host headers and write methods. It binds
only to 127.0.0.1 with a random capability URL and a sandbox CSP denying network
connections/forms. No execution/export endpoints exist. Loopback CSP is defense
in depth, not a replacement for the isolated parent WebEngine profile.

## Persistence and Credentials

Default data root is `core.local_data.ROOT / 'forge'`, honoring the existing
data override. Project workspaces, manifests and immutable hash-checked revisions
live under `projects/<id>/`; undo is limited to tracked project assets and rejects
uncheckpointed edits. Dependencies, dotfiles, environment files and known secret
filenames are excluded from snapshots/export. Snapshots have bounded sizes and
may omit unsupported binary formats. Export requires a host-approved root and
an explicit absolute, nonexistent destination; never overwrites existing data.

`codex-home/` is separate from the desktop Codex home and generated workspaces.
Credentials are owned solely by the official Codex **keyring** backend, forced
by configuration; there is no plaintext fallback or Jarvis credential duplicate.
API keys travel only through local stdin. No desktop credentials are accessed,
copied or migrated. The caller must discard its key after connect. Login URLs
are returned to trusted parent code and are not stored in projects.

`library/<artifact-id>/artifact.json` plus `files/` is a real persistent registry.
`command('list')['library']` reads it. `core.visual_library` is a fixed semantic
recipe catalog and explicitly excludes generated code; it has no registration
API. The parent integrates saved artifacts through `core.forge_artifacts` in
isolated, persistent pinned views; it never mutates the semantic catalog globals.
Thumbnail and framing
remain null until the host supplies actual renderer data.

## Windows Safety and Verified Protocol

Official documentation: https://learn.chatgpt.com/docs/app-server
Installed CLI schemas were generated with `app-server generate-json-schema`
from `2e5e00daee91c61d/codex.exe`, version `0.162.0-alpha.17.2`.
Confirmed initialize/initialized, thread/start/resume, turn/start/steer/interrupt,
account/read/login/start/login/cancel, model/list and windowsSandbox/readiness.

On Windows the owned App Server uses a verified standard-user token, even when
Jarvis is elevated. The launcher validates the official executable signature,
checks the child token before resuming it, and contains descendants in a
kill-on-close job. Launch fails closed if these checks cannot be satisfied. Child tools
receive workspace-write, approvals never, network disabled, no extra temporary
write roots, and a minimal shell environment. Windows readiness must be `ready`
before starting a model turn. This backend never runs generated code itself,
never launches admin shells, and never configures/elevates the Windows sandbox.

**Installed schemas lack restricted read roots. Workspace-write does not imply
host-file confidentiality.** `sandbox.read_isolation` is truthfully false. No
claim of full isolation is made: use a separate Windows account/VM for stronger
read isolation. Model instructions forbid reading private host data, but are not
a security barrier. No paid turn was used to test sandbox enforcement.

Requests have bounded timeouts and bounded protocol/event buffers. Turn watchdog
requests interruption. Cancellation waits for the server's completion event;
if that never arrives, it terminates its owned server and reports failure.
Close interrupts, checkpoints recoverable work, closes preview and protocol
resources, and joins the worker. Leaving the screen should call `save` after
turn completion or preserve a running runtime; it must not silently call close.

Validation: `python -m unittest discover -s tests -p test_forge_backend.py`.
All generation tests use mocks; protocol tests use a real local fake subprocess.
A separate real installed-CLI handshake/status was exercised with a temporary
isolated home, no authentication and no model call. UI/voice/renderer integration
and a paid creation turn remain outside this backend-only delivery.
