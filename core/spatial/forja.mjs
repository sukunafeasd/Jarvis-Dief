// No QWebChannel is installed here or inside the artifact frame.
import {createForgeLight} from './forge-light.mjs';
const panel = document.getElementById('forgePanel'), light = document.getElementById('entranceLight');
const area = document.getElementById('creationArea'), scene = document.getElementById('forgeScene');
const projectedLight=createForgeLight(light);
const list = document.getElementById('stepsContainer'), empty = document.getElementById('emptyState');
let snapshot = {}, generation = 0, pending = null, raf = 0, frame = null, artifactKey = '', serial = 0;
let visible = true, disposed = false, frames = 0;
window.forgeReady = false;
window.forgeScenePhase = 'black';
const command = value => {location.hash = 'forge-command-' + encodeURIComponent(JSON.stringify(value));};
const announce = phase => {
  window.forgeScenePhase = phase;
  document.body.dataset.forgeScene = phase;
  const detail = {phase, generation};
  queueMicrotask(() => {if (detail.generation === generation && detail.phase === window.forgeScenePhase) dispatchEvent(new CustomEvent('forge-scene', {detail}));});
};
function disposePreview() {
  if (frame) {frame.src = 'about:blank'; frame.remove(); frame = null;}
  artifactKey = '';
}
function preview() {
  const url = snapshot.preview_url;
  if (!visible || document.hidden || window.forgeScenePhase !== 'ready' || !url) {disposePreview(); return;}
  let parsed;
  try {parsed = new URL(url, location.href);} catch {disposePreview(); return;}
  // Native host owns authorization; the frame must never gain the parent's origin.
  if (!['file:', 'http:', 'https:', 'blob:'].includes(parsed.protocol)) {disposePreview(); return;}
  const key = parsed.href + ':' + String(snapshot.preview_version ?? '');
  if (key === artifactKey) return;
  disposePreview(); artifactKey = key;
  frame = document.createElement('iframe');
  frame.title = 'Previa do projeto';
  frame.setAttribute('sandbox', 'allow-scripts');
  frame.setAttribute('referrerpolicy', 'no-referrer');
  frame.setAttribute('allow', "camera 'none'; microphone 'none'; geolocation 'none'; clipboard-read 'none'; clipboard-write 'none'");
  frame.src = parsed.href; area.append(frame);
}
function activities(items = []) {
  const scroll = list.scrollTop, atEnd = list.scrollHeight - list.clientHeight - scroll < 24;
  const focused = document.activeElement;
  const nodes = new Map([...list.children].map(node => [node.dataset.id, node]));
  const retained = new Set();
  // The host projects concise PT-BR activity text and owns process semantics.
  for (const [i, item] of items.slice(-3).entries()) {
    const id = String(item.id ?? i); if (retained.has(id)) continue; retained.add(id);
    let node = nodes.get(id);
    if (!node) {
      node = document.createElement('article'); node.dataset.id = id;
      const icon = document.createElement('span'); icon.className = 'step-icon'; icon.setAttribute('aria-hidden', 'true');
      const info = document.createElement('div'); info.className = 'step-info';
      const title = document.createElement('div'); title.className = 'step-name';
      const detail = document.createElement('div'); detail.className = 'step-detail';
      info.append(title, detail); node.append(icon, info); list.append(node);
    }
    const status = ({streaming:'running',inProgress:'running',working:'running',done:'completed',ok:'completed'})[item.status] || (['running','completed','failed','pending','waiting'].includes(item.status) ? item.status : 'pending');
    node.className = 'step-item ' + status;
    node.querySelector('.step-icon').textContent = {running:'\u22ef',completed:'\u2713',failed:'!',pending:'\u00b7',waiting:'\u2016'}[status];
    node.querySelector('.step-name').textContent = String(item.title ?? 'Atividade');
    node.querySelector('.step-detail').textContent = String(item.detail ?? '');
    let progress = node.querySelector('progress');
    if (typeof item.progress === 'number' && Number.isFinite(item.progress)) {
      if (!progress) {progress = document.createElement('progress'); progress.max = 100; node.querySelector('.step-info').append(progress);}
      progress.value = Math.max(0, Math.min(100, item.progress)); progress.setAttribute('aria-label', String(item.title ?? 'Progresso'));
    } else progress?.remove();
    list.append(node);
  }
  for (const node of [...list.children]) if (!retained.has(node.dataset.id)) node.remove();
  empty.hidden = retained.size > 0;
  list.scrollTop = atEnd ? list.scrollHeight : scroll;
  if (focused && document.contains(focused) && document.activeElement !== focused) focused.focus({preventScroll:true});
}
window.updateForge = value => {
  if (!value || typeof value !== 'object' || disposed) return;
  snapshot = {...snapshot, ...value};
  visible = snapshot.visible !== false;
  document.getElementById('modelStatus').textContent = String(snapshot.engine ?? 'Aguardando conexao');
  document.getElementById('projectName').textContent = String(snapshot.project ?? '');
  document.body.dataset.workState = String(snapshot.state ?? 'idle');
  if (Array.isArray(snapshot.activities)) activities(snapshot.activities);
  preview();
};
function finish(status) {
  cancelAnimationFrame(raf); raf = 0;
  const request = pending; pending = null;
  request?.resolve({phase:window.forgeScenePhase, generation:request.generation, status});
}
function animate(exiting, options = {}) {
  if (disposed) return Promise.reject(new Error('FORJA scene disposed'));
  if (!window.forgeReady) return Promise.reject(new Error('FORJA assets not ready'));
  if (pending?.exiting === exiting) return pending.promise;
  if (!pending && window.forgeScenePhase === (exiting ? 'exited' : 'ready')) return Promise.resolve({phase:window.forgeScenePhase, generation, status:'completed'});
  if (pending) finish('superseded');
  generation++;
  const reduced = options.reduced ?? matchMedia('(prefers-reduced-motion: reduce)').matches;
  const duration = reduced ? 300 : exiting ? 700 : 2200;
  let resolve;
  const promise = new Promise(done => {resolve = done;});
  pending = {promise, resolve, generation, exiting};
  let elapsed = 0, previous = performance.now();
  announce(exiting ? 'exiting' : 'panel_emerging');
  panel.inert = true; disposePreview(); area.style.opacity = '0';
  const fromOpacity = Number(panel.style.opacity || 0);
  const bounds = panel.getBoundingClientRect();
  function tick(now) {
    if (!pending) return;
    const dt = Math.max(0, Math.min(100, now - previous)); previous = now;
    if (visible && !document.hidden) {
      elapsed += dt; const p = Math.min(1, elapsed / duration); frames++;
      if (exiting) {
        projectedLight.clear(); panel.style.clipPath='none';
        panel.style.opacity = String(fromOpacity * (1 - p));
        const tremor = reduced ? 0 : Math.sin(p * 28) * (1 - p) * 2;
        scene.style.transform = `translate(${tremor}px,${tremor * .4}px)`;
        document.getElementById('exitLight').style.opacity = reduced ? '0' : String(Math.sin(p * Math.PI) * .07);
      } else {
        const scan=Math.max(0,Math.min(1,(p-.61)/.35)), reveal=scan*scan*(3-2*scan);
        projectedLight.draw(p,bounds,reduced);
        panel.style.visibility = 'visible';
        panel.style.opacity = String(fromOpacity + (1-fromOpacity)*Math.min(1,reveal*2));
        panel.style.clipPath=reduced ? 'none' : `inset(0 0 ${(1-reveal)*100}% 0)`;
      }
      if (p === 1) {
        projectedLight.clear();panel.style.clipPath='none';scene.style.transform = ''; document.getElementById('exitLight').style.opacity = '0';
        panel.style.opacity = exiting ? '0' : '1'; panel.style.visibility = exiting ? 'hidden' : 'visible'; panel.inert = exiting;
        area.style.opacity = exiting ? '0' : '1'; announce(exiting ? 'exited' : 'ready'); preview(); finish('completed'); return;
      }
    }
    raf = requestAnimationFrame(tick);
  }
  raf = requestAnimationFrame(tick); return promise;
}
window.beginForgeEntrance = options => animate(false, options);
window.exitForgeScene = options => animate(true, options);
window.forgeDiagnostics = () => ({phase:window.forgeScenePhase, ready:window.forgeReady, generation, frames, visible, scheduled:Boolean(raf), previewActive:Boolean(frame), previewSandbox:frame?.getAttribute('sandbox') ?? null, light:projectedLight.diagnostics(), activities:list.children.length});
document.getElementById('promptForm').addEventListener('submit', event => {
  event.preventDefault(); const input = document.getElementById('forgePrompt'), prompt = input.value.trim();
  if (!prompt || window.forgeScenePhase !== 'ready') return;
  command({action:'prompt', prompt, serial:++serial}); input.value = '';
});
document.getElementById('forgePrompt').addEventListener('keydown', event => {
  if (event.key === 'Enter' && !event.shiftKey && !event.repeat && !event.isComposing) {
    event.preventDefault(); document.getElementById('promptForm').requestSubmit();
  }
});
addEventListener('keydown', event => {if (event.key === 'F11' && !event.repeat) {event.preventDefault(); location.hash = 'window-fullscreen-' + (++serial);}});
document.addEventListener('visibilitychange', preview);
addEventListener('pagehide', () => {disposed = true; window.forgeReady = false; disposePreview(); announce('exited'); finish('disposed');});
// Passive black is render-ready; entrance is exclusively initiated by the parent.
// Qt may preload this page hidden: DOM/module readiness must not require a frame.
window.forgeReady = true; document.body.dataset.ready = 'true'; announce('black');
