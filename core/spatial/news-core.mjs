import * as THREE from 'three';

const clean = (value, limit = 180) => String(value ?? '').slice(0, limit);
const imageAllowed = value => typeof value === 'string' && value.length < 12000000 &&
  /^data:image\/(png|jpeg|webp);base64,/.test(value);

function wrap(ctx, text, x, y, width, lineHeight, maxLines) {
  const drawLine=(line,row)=>{
    if(ctx.measureText(line).width>width){
      while(line.length && ctx.measureText(line+'…').width>width)line=line.slice(0,-1);
      line+='…';
    }
    ctx.fillText(line,x,y+row*lineHeight);
  };
  const words = clean(text, 400).split(/\s+/);
  let line = '', row = 0;
  for (let index=0;index<words.length;index++) {
    const word=words[index];
    const next = line ? line + ' ' + word : word;
    if (ctx.measureText(next).width > width && line) {
      drawLine(line,row++);
      line = word;
      if (row === maxLines - 1) {
        line=words.slice(index).join(' ');
        break;
      }
    } else line = next;
  }
  if (row < maxLines) {
    drawLine(line,row);
  }
}

// Three bounded ribbons share the primary core's camera, shell and render loop.
export class NewsCoreProjection {
  constructor(root, glowTexture) {
    this.root = root;
    this.group = new THREE.Group();
    this.group.userData.newsProjection = true;
    root.add(this.group);
    this.ribbons=new THREE.Group();this.group.add(this.ribbons);
    const rails=[],nodes=[];
    for(const y of [1.13,.47,.33,-.33,-.47,-1.13]) {
      const radius=Math.sqrt(1.52*1.52-y*y);
      for(let i=0;i<120;i++) {
        if(i%19===0)continue;
        for(const j of [i,i+1]) {
          const a=j/120*Math.PI*2;
          rails.push(Math.cos(a)*radius,y,Math.sin(a)*radius);
        }
      }
      for(const x of [-.95,.95]) nodes.push(x,y,Math.sqrt(Math.max(0,1.52*1.52-y*y-x*x)));
    }
    this.rails=new THREE.LineSegments(
      new THREE.BufferGeometry().setAttribute('position',new THREE.Float32BufferAttribute(rails,3)),
      new THREE.LineBasicMaterial({color:'#ff303b',transparent:true,opacity:.55,depthWrite:false,blending:THREE.AdditiveBlending}));
    this.nodes=new THREE.Points(
      new THREE.BufferGeometry().setAttribute('position',new THREE.Float32BufferAttribute(nodes,3)),
      new THREE.PointsMaterial({color:'#ff7055',size:.22,map:glowTexture,transparent:true,opacity:.9,depthTest:false,depthWrite:false,blending:THREE.AdditiveBlending}));
    this.nodes.renderOrder=2;
    for(const node of [this.rails,this.nodes]){node.userData.newsProjection=true;this.group.add(node);}
    this.rows = [];
    this.signature = '';
    this.generation = 0;
    this.progress = 0;
    this.phase = 'fused';
    this.focus = 0;
    this.revealed = new Set([0]);
  }

  update(value) {
    if(this.id!==value.id) {
      this.id=value.id;this.revealed=new Set();this.progress=0;
    }
    const items = Array.isArray(value.items) ? value.items.slice(0, 24) : [];
    this.focus = Math.max(0, Math.min(items.length - 1, Math.trunc(Number(value.focus) || 0)));
    this.revealed.add(this.focus);
    this.phase = value.mode || 'fused';
    if(this.phase==='settled')items.forEach((_,index)=>this.revealed.add(index));
    const start = Math.floor(this.focus / 3) * 3;
    const page = items.slice(start, start + 3);
    const signature = JSON.stringify([value.id, start, page]);
    if (signature !== this.signature) {
      this.clear();
      this.signature = signature;
      const generation = this.generation;
      page.forEach((item, slot) => this.addRow(item, start + slot, slot, generation));
    }
    this.rows.forEach(row => {
      row.material.uniforms.accent.value.set(value.color || '#ff303b');
      if(row.color!==value.color){row.color=value.color;this.paint(row);}
    });
    this.rails.material.color.set(value.color || '#ff303b');
    this.nodes.material.color.set(value.color || '#ff303b').lerp(new THREE.Color('#ffe3be'),.3);
    this.accessible(items);
  }

  accessible(items) {
    let summary = document.getElementById('core-news-summary');
    if (!summary) {
      summary = document.createElement('section');
      summary.id = 'core-news-summary';
      summary.setAttribute('aria-label', 'Notícias apresentadas pelo Jarvis');
      summary.style.cssText = 'position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);pointer-events:none';
      document.body.append(summary);
    }
    summary.textContent = items.map(item => [item.title, item.source, item.detail].filter(Boolean).join('. ')).join('\n');
  }

  addRow(item, index, slot, generation) {
    const canvas = document.createElement('canvas');
    canvas.width = 1400; canvas.height = 320;
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.generateMipmaps = false;
    texture.minFilter = THREE.LinearFilter;
    const geometry = new THREE.PlaneGeometry(2.68, .64, 36, 8);
    const y = .80 - slot * .80;
    const positions = geometry.attributes.position;
    for (let i = 0; i < positions.count; i++) {
      const x = positions.getX(i), py = positions.getY(i) + y;
      positions.setXYZ(i, x, py, .82 * Math.sqrt(Math.max(.01, 1.48*1.48-x*x-py*py)));
    }
    geometry.computeVertexNormals();
    const material = new THREE.ShaderMaterial({
      transparent: true, depthWrite: true, depthTest: true,
      uniforms: {sheet:{value:texture}, alpha:{value:0}, focus:{value:0}, scan:{value:0}, accent:{value:new THREE.Color('#ff303b')}},
      vertexShader: `varying vec2 uvSheet;varying vec2 localPoint;
        void main(){uvSheet=uv;localPoint=position.xy;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
      fragmentShader: `varying vec2 uvSheet;varying vec2 localPoint;
        uniform sampler2D sheet;uniform float alpha,focus,scan;uniform vec3 accent;
        void main(){
          float radial=length(localPoint);
          float edge=1.-smoothstep(1.34,1.47,radial);
          float heart=smoothstep(.30,.42,radial);
          vec4 pixel=texture2D(sheet,uvSheet);
          float reveal=smoothstep(-.08,.05,scan-uvSheet.x);
          float a=pixel.a*edge*heart*alpha*reveal;
          if(a<.025)discard;
          float seam=pow(1.-abs(uvSheet.y*2.-1.),36.);
          float beam=exp(-abs(uvSheet.x-scan)*95.)*.16;
          gl_FragColor=vec4(pixel.rgb*(.76+.24*focus)+accent*(beam+seam*.012),a);
          #include <colorspace_fragment>
        }`,
    });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.userData.newsProjection = true;
    // Draw before the shell: front filaments survive depth testing, back wires recede.
    mesh.renderOrder = -2;
    this.ribbons.add(mesh);
    const row = {mesh, material, texture, canvas, item, index, slot, image:null, reveal:0};
    this.rows.push(row);
    this.paint(row);
    if (imageAllowed(item.image)) {
      const image = new Image();
      row.loader = image;
      image.onload = () => {
        if (this.generation !== generation || !this.rows.includes(row)) return;
        row.image = image;
        this.paint(row);
        this.invalidate?.();
      };
      image.src = item.image;
    }
  }

  paint(row) {
    const ctx = row.canvas.getContext('2d');
    const {item, image, slot} = row;
    ctx.clearRect(0, 0, 1400, 320);
    const middle = slot === 1;
    const imageWidth = middle ? 470 : 650;
    const textX = middle ? 890 : 750;
    ctx.fillStyle = 'rgba(0,9,16,.90)';
    ctx.fillRect(35, 14, imageWidth, 292);
    ctx.fillRect(textX - 18, 14, 1390 - textX, 292);
    if (image) {
      const ratio = Math.max(imageWidth / image.naturalWidth, 292 / image.naturalHeight);
      ctx.save();ctx.beginPath();ctx.roundRect(35, 14, imageWidth, 292, 18);ctx.clip();
      ctx.drawImage(image, 35 + (imageWidth - image.naturalWidth * ratio) / 2,
        14 + (292 - image.naturalHeight * ratio) / 2, image.naturalWidth * ratio, image.naturalHeight * ratio);
      ctx.restore();
    } else {
      ctx.fillStyle = '#8daab7';ctx.font = '30px Segoe UI, sans-serif';
      ctx.fillText('Imagem não disponível', 65, 166);
    }
    ctx.strokeStyle=row.color || '#ff5459';ctx.lineWidth=2;
    ctx.beginPath();ctx.moveTo(35,20);ctx.lineTo(35,14);ctx.lineTo(90,14);
    ctx.moveTo(imageWidth-20,306);ctx.lineTo(imageWidth+35,306);ctx.lineTo(imageWidth+35,290);
    ctx.stroke();
    ctx.fillStyle = row.color || '#ff5459';ctx.font = '600 34px Segoe UI, sans-serif';
    ctx.fillText(clean(item.category || 'NOTÍCIAS', 26).toLocaleUpperCase('pt-BR'), textX, 57, 1360-textX);
    ctx.fillStyle = '#f0faff';ctx.font = '500 48px Segoe UI, sans-serif';
    wrap(ctx, clean(item.title, 400), textX, 113, 1360 - textX, 51, 3);
    ctx.fillStyle = '#9cc1d2';ctx.font = '28px Segoe UI, sans-serif';
    const published=item.time || item.published || '';
    ctx.fillText(clean([item.source,published].filter(Boolean).join(' · '),70), textX, 292,1360-textX);
    row.texture.needsUpdate = true;
  }

  step(dt, input) {
    const reduced = input.motion === 'reduced';
    if (this.phase !== 'paused') this.progress = reduced ? 1 : Math.min(1, this.progress + dt / .58);
    const exit = this.phase === 'front';
    if (exit) this.exit = reduced ? 1 : Math.min(1, (this.exit || 0) + dt / .58);
    else this.exit = 0;
    const out = this.exit || 0;
    this.rails.material.opacity=.55*(1-out)*(input.resting ? .15 : 1)*this.progress;
    this.nodes.material.opacity=.9*(1-out)*(input.resting ? .15 : 1)*this.progress;
    this.rows.forEach(row => {
      const visible = this.revealed.has(row.index);
      if (this.phase !== 'paused' && visible) row.reveal = reduced ? 1 : Math.min(1, row.reveal + dt / .52);
      row.material.uniforms.scan.value = row.reveal * 1.12;
      row.material.uniforms.focus.value = row.index === this.focus ? 1 : .6;
      row.material.uniforms.alpha.value = (1 - out) * (row.index === this.focus ? .98 : .90) * (input.resting ? .15 : 1);
      row.mesh.visible = visible;
      row.mesh.position.z = reduced ? 0 : out * .78;
      row.mesh.scale.setScalar(1 + out * .10);
    });
    return exit && out === 1;
  }

  clear() {
    this.generation++;
    for (const row of this.rows) {
      if (row.loader) {row.loader.onload = null;row.loader.onerror = null;row.loader.src = '';}
      row.mesh.geometry.dispose();row.material.dispose();row.texture.dispose();
    }
    this.ribbons.clear();this.rows = [];
  }

  dispose() {
    this.clear();this.root.remove(this.group);
    for(const node of [this.rails,this.nodes]){node.geometry.dispose();node.material.dispose();}
    document.getElementById('core-news-summary')?.remove();
  }

  diagnostics() {
    return {phase:this.phase, focus:this.focus, rows:this.rows.length,
      progress:this.progress,
      visible:this.rows.filter(row=>row.mesh.visible).map(row=>row.index),
      images:this.rows.filter(row=>row.image).length, exit:this.exit || 0};
  }
}
