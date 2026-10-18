import { surfaceFor } from './projection-style.mjs';
// Cached decorative glass, below WebGL and DOM. No extra animation scheduler.
export class HudSurface {
  constructor(body) {
    this.body = body;
    this.canvas = document.createElement('canvas');
    this.key = '';
    this.renders = 0;
    this.anchors = [];
    this.measuredAt = 0;
    this.projectionKey = '';
  }

  update(model, width, height) {
    const fact = this.body.dataset.factSymbol || '';
    const hidden = Boolean(model.framed) || surfaceFor(model)!=='card';
    const scale = Math.min(devicePixelRatio || 1, 1.5);
    const projectionKey = [width, height, fact].join(':');
    const now = performance.now();
    if (projectionKey !== this.projectionKey || now - this.measuredAt > 120) {
      this.projectionKey = projectionKey;
      this.measuredAt = now;
      this.anchors = fact && width > 430 ? [...this.body.querySelectorAll('.record h2')].slice(0, 4).map(label => {
        const bounds = label.getBoundingClientRect();
        return [Math.round(bounds.left), Math.round(bounds.top + bounds.height / 2)];
      }) : [];
    }
    const anchors = this.anchors;
    const key = [width, height, scale, hidden, fact, !!model.compact, JSON.stringify(anchors)].join(':');
    if (key === this.key) return;
    this.key = key;
    if (hidden) {
      this.body.style.setProperty('--hud-surface', 'none');
      return;
    }
    this.canvas.width = Math.max(1, Math.round(width * scale));
    this.canvas.height = Math.max(1, Math.round(height * scale));
    const c = this.canvas.getContext('2d');
    c.scale(scale, scale);
    const w = width, h = height, inset = 5, cut = model.compact ? 10 : 18;
    const path = () => {
      c.beginPath();
      c.roundRect(inset,inset,w-inset*2,h-inset*2,14);
    };
    c.save();
    if (!fact) { path(); c.clip(); }
    const glass = c.createLinearGradient(0, 0, w * .75, h);
    glass.addColorStop(0, fact ? '#003d6b00' : '#082438fa');
    glass.addColorStop(.23, fact ? '#00437835' : '#03131ffa');
    glass.addColorStop(.72, fact ? '#022d5625' : '#020d18fa');
    glass.addColorStop(1, fact ? '#001d4100' : '#06334dfa');
    c.fillStyle = glass; c.fillRect(0, 0, w, h);
    // Blueprint lattice fades below long text; stronger around spatial symbols.
    const wash = c.createRadialGradient(w * .3, h * .43, 0, w * .3, h * .43, Math.max(w, h) * .7);
    wash.addColorStop(0, fact ? '#1679b343' : '#0fcde71c');
    wash.addColorStop(1, '#00b9df00'); c.fillStyle = wash; c.fillRect(0, 0, w, h);
    for (let x = 16; x < w; x += 24) {
      c.strokeStyle = x % 120 === 16 ? '#45bfeb19' : '#39bfe60b';
      c.beginPath(); c.moveTo(x, 16); c.lineTo(x, h - 16); c.stroke();
    }
    for (let y = 16; y < h; y += 24) {
      c.strokeStyle = y % 120 === 16 ? '#45bfeb19' : '#39bfe60b';
      c.beginPath(); c.moveTo(16, y); c.lineTo(w - 16, y); c.stroke();
    }
    c.fillStyle = '#b2eaff12';
    for (let y = 16; y < h; y += 48) for (let x = 16; x < w; x += 48) {
      c.fillRect(x - 2, y, 5, 1); c.fillRect(x, y - 2, 1, 5);
    }
    const reflection = c.createLinearGradient(0, 0, w, h * .6);
    reflection.addColorStop(0, '#dcfaff16'); reflection.addColorStop(.25, '#bcf6ff03');
    reflection.addColorStop(.4, '#bcf6ff00'); reflection.addColorStop(1, '#bcf6ff00');
    c.fillStyle = reflection; c.fillRect(0, 0, w, h);
    c.restore();
    if (fact) {
      const color = fact === 'energy' ? '#40f3a7' : '#ffbc45';
      c.strokeStyle = color; c.fillStyle = color; c.shadowColor = color; c.shadowBlur = 7;
      for (const [x, y] of anchors) {
        c.beginPath(); c.moveTo(x - 42, y); c.lineTo(x - 8, y); c.stroke();
        c.beginPath(); c.arc(x - 42, y, 2, 0, Math.PI*2); c.fill();
      }
      c.shadowBlur = 0;
    }
    if (!fact) {
      // Separate bevel, luminous conductor and fine specular edge give the frame thickness.
      for (const [size, color, glow] of [[8, '#2885bb20', 8], [2, '#5ebbf0a0', 3], [1, '#c9efffcc', 0]]) {
        path(); c.lineWidth = size; c.strokeStyle = color; c.shadowBlur = glow; c.stroke();
      }
      for (const [x, y, sx, sy] of [[inset,inset,1,1],[w-inset,inset,-1,1],
        [inset,h-inset,1,-1],[w-inset,h-inset,-1,-1]]) {
        c.beginPath(); c.moveTo(x, y + sy * Math.min(55, h / 3));
        c.lineTo(x, y + sy * cut); c.lineTo(x + sx * cut, y);
        c.lineTo(x + sx * Math.min(82, w / 3), y);
        for (const [size, color, blur] of [[7,'#2585c024',14],[3,'#69caffc0',8],[1,'#ddf4ff',2]]) {
          c.lineWidth = size; c.strokeStyle = color; c.shadowColor = '#57bfff';
          c.shadowBlur = blur; c.stroke();
        }
      }
      c.shadowColor = '#00dffa'; c.shadowBlur = 7;
      c.strokeStyle = '#39e8f5c0'; c.lineWidth = 1;
      c.beginPath(); c.moveTo(w * .56, inset); c.lineTo(w * .76, inset); c.stroke();
      c.shadowBlur = 0;
      c.strokeStyle = '#5fddeb28';
      for (let y = 72; y < h - 60; y += 9) {
        c.beginPath(); c.moveTo(w - 10, y); c.lineTo(w - 13, y); c.stroke();
      }
    }
    this.body.style.setProperty('--hud-surface', `url("${this.canvas.toDataURL()}")`);
    this.body.dataset.hudPaints = String(++this.renders);
  }

  dispose() {
    this.body.style.removeProperty('--hud-surface');
    this.canvas.width = this.canvas.height = 1;
    this.key = '';
    this.anchors = [];
  }
}
