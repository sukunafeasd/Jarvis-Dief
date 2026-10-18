# FORJA frontend / native parent contract

All assets are local. The primary core is `index.html` / `viewer.mjs`, using its
existing model, materials, camera and renderer. `space.html` only fades the
background. No duplicate core or new Three distribution is created.

## Parent sequence

1. Save native geometries and visibility; hide chrome and pins. Expand the actual
   `hud._spatial_core` WebEngine to the stage before beginning. Keep both pages
   visible (`updateCore({visible:true})`) until their transitions complete.
2. Call `window.enterForgeTransition({motion:'full'})` on both pages. Each returns
   a Promise of `{phase,generation,status,role}`. Repeated calls share the active
   Promise. `window.forgeTransitionPhase` becomes `blackout` after the last rendered
   frame is covered in absolute black. The primary page moves the real camera.
3. Overlay `forja.html`, which starts passive and completely black. Wait for
   `window.forgeReady === true` (module and initial DOM frame ready; there is no
   second renderer in this page). Then call
   `window.beginForgeEntrance({reduced:false})`; its Promise completes with
   `window.forgeScenePhase === 'ready'` after the white light forms the side panel.
4. Native speech may announce readiness only at this point. Hide underlying views
   and synchronize real events with `updateForge`.
5. On exit, persist the project in the parent; set FORJA visible if necessary;
   await `exitForgeScene({reduced:false})`, which sets scene phase `exited` on black.
   Show underlying views while still black, remove FORJA, then await
   `exitForgeTransition({motion:'full'})` on both pages. Their phase becomes
   `normal`. Restore native geometry, chrome and pins, then announce exit once.

Qt `runJavaScript` does not await JS Promises automatically. Poll phase and
diagnostics or attach a JS completion callback to the parent's existing channel.
The events `forge-transition` and `forge-scene` contain phase and generation.
Success requires `status:'completed'`; interrupted operations settle with
`superseded`, `disposed`, `failed` or `context-lost`. The parent should enforce a
timeout and restore native visibility on failure. Hidden time does not consume
animation time; a parent must not wait for completion while hiding that page.
The booleans `reduced:true` and `motion:'reduced'` avoid camera travel and tremor.

## Snapshot and commands

`window.updateForge({visible:true, state:'validating', engine:'Codex',
project:'Planeta com aneis', activities:[{id:'test',title:'Executando testes',
detail:'Resultado publico',status:'running',progress:42}],
preview_url:'file:///C:/project/preview.html', preview_version:3})`.

Snapshots merge supplied top-level fields. Use `preview_url:null` or
`activities:[]` to clear them. Activities are observable public work only;
statuses are `pending`, `running`, `completed`, `failed`, `waiting`. Numeric
progress appears only for a finite number supplied by the host. Up to 150 recent
activity entries are retained, keyed by stable IDs. Absent events stay empty.
The frontend does not connect to Codex, generate projects or infer completion.

Commands change only the page fragment:
`#forge-command-` + `encodeURIComponent(JSON.stringify({action:'prompt',prompt,
serial}))`, or `{action:'exit',serial}`. The native LocalPage URL callback must
decode and validate action and payload, deduplicate serials per page/session,
and route them to the host. F11 emits `#window-fullscreen-<serial>`.
No Qt bridge is installed in FORJA or in the generated artifact.

The artifact iframe has exactly `sandbox="allow-scripts"`, with no same-origin,
navigation, popup, download, form or Qt permission. Local or HTTP assets inside
generated pages must work with an opaque sandbox origin (use a parent-approved
loopback preview server with appropriate CORS when file module loading requires
it). The parent authorizes and serves the URL. Hidden/exited previews are removed,
including their browsing context; re-showing loads a fresh preview from the latest
snapshot. Preview version changes reload without rebuilding the activity panel.

Diagnostics: `forgeTransitionDiagnostics()` on both scene pages;
`forgeDiagnostics()` on FORJA. Native lifecycle, speech and backend routing are
the parent controller's responsibility. This change does not modify Python,
settings, stored projects or credentials.

Validation: run `tools/validate_forja_frontend.py` with the project's Python.
It checks primary camera travel, absolute black pixels, desktop/mobile layout,
generated animation, sandbox isolation, disposal, reentry, resize and hash commands.
