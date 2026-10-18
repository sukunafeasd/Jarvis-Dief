// The parent calls both pages; only the primary page receives the existing core.
export function installForgeTransition({scene, camera, renderer, core = null, getState}) {
  let phase = 'normal', generation = 0, pending = null, raf = 0, elapsed = 0, saved = null, pose = 0;
  const black = document.createElement('div');
  black.setAttribute('aria-hidden', 'true');
  black.style.cssText = 'position:fixed;inset:0;background:#000;opacity:0;pointer-events:none;z-index:2147483647';
  document.body.append(black);
  const announce = value => {
    phase = window.forgeTransitionPhase = value;
    document.body.dataset.forgeTransition = value;
    const detail = {phase, generation, role:core ? 'core' : 'background'};
    queueMicrotask(() => {if (detail.generation === generation && detail.phase === phase) window.dispatchEvent(new CustomEvent('forge-transition', {detail}));});
  };
  function capture() {
    const materials = new Map(), nodes = new Map();
    scene.traverse(node => {
      nodes.set(node, {visible:node.visible, position:node.position.clone(), rotation:node.rotation.clone(), scale:node.scale.clone()});
      for (const material of (Array.isArray(node.material) ? node.material : [node.material])) {
        if (!material || materials.has(material)) continue;
        const uniforms = {};
        for (const key of ['visibility', 'energy', 'activity', 'time']) if (material.uniforms?.[key]) uniforms[key] = material.uniforms[key].value;
        materials.set(material, {opacity:material.opacity, transparent:material.transparent, uniforms});
      }
    });
    const coreMaterials = new Set();
    core?.root.traverse(node => {for (const m of (Array.isArray(node.material) ? node.material : [node.material])) if (m) coreMaterials.add(m);});
    const target = core?.root.getWorldPosition(camera.position.clone());
    const orientation = camera.clone();
    if (target) {orientation.position.copy(camera.position); orientation.lookAt(target.x, target.y, target.z - .1);}
    return {materials, nodes, coreMaterials, target, orientation:orientation.quaternion.clone(), position:camera.position.clone(), quaternion:camera.quaternion.clone(), baseDistance:camera.userData.baseDistance, background:document.body.style.background};
  }
  function restore(final = true) {
    if (!saved) return;
    const currentDistance=camera.userData.baseDistance;
    if(core&&Number.isFinite(currentDistance)&&Number.isFinite(saved.baseDistance)&&currentDistance!==saved.baseDistance){
      saved.position.z+=currentDistance-saved.baseDistance;saved.baseDistance=currentDistance;
      const orientation=camera.clone();orientation.position.copy(saved.position);
      orientation.lookAt(saved.target.x,saved.target.y,saved.target.z-.1);
      saved.orientation.copy(orientation.quaternion);
    }
    saved.materials.forEach((value, material) => {
      material.opacity = value.opacity;
      if (final && material.transparent !== value.transparent) {material.transparent = value.transparent; material.needsUpdate = true;}
      for (const [key, original] of Object.entries(value.uniforms)) material.uniforms[key].value = original;
    });
    saved.nodes.forEach((value, node) => {
      node.visible = value.visible; node.position.copy(value.position); node.rotation.copy(value.rotation); node.scale.copy(value.scale);
    });
    camera.position.copy(saved.position); camera.quaternion.copy(saved.quaternion); camera.updateMatrixWorld();
  }
  function settle(status) {
    cancelAnimationFrame(raf); raf = 0;
    const request = pending; pending = null;
    request?.resolve({phase, generation:request.generation, status, role:core ? 'core' : 'background'});
  }
  function abort(reason = 'cancelled') {
    restore(); black.style.opacity = '0';
    if (saved) document.body.style.background = saved.background;
    saved = null; pose = 0; announce('normal'); settle(reason);
  }
  function draw(progress, exiting, reduced) {
    pose = progress;
    restore(false);
    const duration = reduced ? .3 : 5;
    const t = progress * duration;
    const preparation = reduced ? progress : Math.min(1, t / 2);
    const approach = reduced ? 0 : Math.min(1, t / 4.7);
    const ease = approach * approach * (3 - 2 * approach);
    const fade = reduced ? progress : Math.max(0, Math.min(1, (t - 4.45) / .55));
    const coreMaterials = saved.coreMaterials;
    if (core) {
      core.root.visible = true;
      // Drive the actual model's rings and energy uniforms, never a replacement mesh.
      if (!reduced) {
        core.rings.rotation.z += t * (.3 + preparation * 2);
        core.rings.children.forEach((ring, i) => {ring.rotation.y += t * (i % 2 ? -1 : 1) * preparation;});
      }
      coreMaterials.forEach(material => {
        const original = saved.materials.get(material).uniforms;
        if (!reduced && material.uniforms?.time) material.uniforms.time.value = original.time + t;
        if (material.uniforms?.energy) material.uniforms.energy.value = original.energy + preparation * .6;
        if (material.uniforms?.activity) material.uniforms.activity.value = original.activity + preparation * .6;
      });
      const target = saved.target;
      camera.position.lerpVectors(saved.position, target, ease);
      camera.quaternion.slerpQuaternions(saved.quaternion, saved.orientation, ease);
    }
    black.style.opacity = String(fade);
    camera.updateMatrixWorld(); scene.updateMatrixWorld(true); renderer.render(scene, camera);
    const next = exiting ? 'exiting' : t < (reduced ? .15 : 2) ? 'preparing' : 'entering_core';
    if (phase !== next) announce(next);
  }
  function start(exiting, options = {}) {
    if (pending?.exiting === exiting) return pending.promise;
    if (!exiting && phase === 'blackout') return Promise.resolve({phase, generation, status:'completed'});
    if (exiting && phase === 'normal' && !pending) return Promise.resolve({phase, generation, status:'completed'});
    if (!renderer) return Promise.reject(new Error('FORJA renderer unavailable'));
    if (pending) settle('superseded');
    if (!saved) {saved = capture(); pose = 0;}
    generation++; elapsed = 0;
    const reduced = options.reduced ?? (options.motion === 'reduced' || getState().motion === 'reduced' || matchMedia('(prefers-reduced-motion: reduce)').matches);
    const from = pose;
    const duration = reduced ? .3 : exiting ? Math.max(.3, 2 * from) : Math.max(.3, 5 * (1 - from));
    let resolve;
    const promise = new Promise(done => {resolve = done;});
    pending = {promise, resolve, generation, exiting};
    announce(exiting ? 'exiting' : 'preparing');
    let previous = performance.now();
    function frame(now) {
      if (!pending) return;
      const dt = Math.max(0, Math.min(.1, (now - previous) / 1000)); previous = now;
      if (!document.hidden && getState().visible !== false) {
        elapsed += dt;
        const p = Math.min(1, elapsed / duration);
        try {draw(exiting ? from * (1 - p) : from + (1 - from) * p, exiting, reduced);} catch (error) {abort('failed'); window.forgeTransitionError = String(error); return;}
        if (p === 1) {
          if (exiting) {
            restore(); document.body.style.background = saved.background; saved = null; pose = 0; black.style.opacity = '0';
            renderer.render(scene, camera); announce('normal');
          } else {black.style.opacity = '1'; announce('blackout');}
          settle('completed'); return;
        }
      }
      raf = requestAnimationFrame(frame);
    }
    raf = requestAnimationFrame(frame);
    return promise;
  }
  window.enterForgeTransition = options => start(false, options);
  window.exitForgeTransition = options => start(true, options);
  window.forgeTransitionDiagnostics = () => ({phase, generation, elapsed, active:phase !== 'normal', role:core ? 'core' : 'background', camera:camera.position.toArray(), blackoutOpacity:Number(black.style.opacity), scheduled:Boolean(raf)});
  addEventListener('pagehide', () => {abort('disposed'); black.remove();});
  renderer?.domElement.addEventListener('webglcontextlost', () => abort('context-lost'));
  announce('normal');
  return {get active() {return phase !== 'normal';}};
}
