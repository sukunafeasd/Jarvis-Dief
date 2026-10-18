// One projected light draws the panel into view; the canvas stays transparent.
const clamp = value => Math.max(0, Math.min(1, value));
const smooth = value => {const p = clamp(value); return p * p * (3 - 2 * p);};

function location(progress, bounds, width, height) {
  const travel = smooth((progress - .18) / .43);
  const scan = smooth((progress - .61) / .35);
  const start = {x:width * .5, y:height * .5};
  const end = {x:bounds.left + bounds.width * .5, y:bounds.top};
  if (progress >= .61) return {x:end.x, y:end.y + bounds.height * scan, scan};
  const control = {x:start.x + (end.x - start.x) * .55, y:Math.max(30, Math.min(start.y, end.y) - height * .14)};
  const a = 1 - travel;
  return {x:a*a*start.x + 2*a*travel*control.x + travel*travel*end.x,
          y:a*a*start.y + 2*a*travel*control.y + travel*travel*end.y, scan:0};
}

export function createForgeLight(canvas) {
  const ctx = canvas.getContext('2d', {alpha:true});
  let width=0, height=0, ratio=1, frames=0, last=null;
  function resize() {
    const nextRatio=Math.min(devicePixelRatio || 1, 1.5);
    if (width===innerWidth && height===innerHeight && ratio===nextRatio) return;
    width=innerWidth; height=innerHeight; ratio=nextRatio;
    canvas.width=Math.round(width*ratio); canvas.height=Math.round(height*ratio);
    ctx.setTransform(ratio,0,0,ratio,0,0);
  }
  function clear() {
    if (ctx) ctx.clearRect(0,0,width,height);
    canvas.style.opacity='0'; last=null;
  }
  function draw(progress,bounds,reduced=false) {
    if (!ctx) return;
    resize(); ctx.clearRect(0,0,width,height); frames++;
    const p=clamp(progress), point=location(p,bounds,width,height);
    const envelope=smooth(p/.09)*(1-smooth((p-.91)/.09));
    const radius=(3 + 4*Math.sin(p*Math.PI))*(reduced ? .65 : 1);
    canvas.style.opacity=String(envelope*(reduced ? .35 : 1));
    ctx.globalCompositeOperation='screen';
    // A bounded history along the same trajectory gives a soft, coherent wake.
    const trail=[];
    for(let i=0;i<34;i++) {
      const sample=location(Math.max(0,p-i*.0055),bounds,width,height);
      if (!trail.length || Math.hypot(sample.x-trail.at(-1).x,sample.y-trail.at(-1).y)>.8) trail.push(sample);
    }
    if (!reduced && trail.length>1) {
      for (const [lineWidth,alpha,blur] of [[26,.07,18],[10,.16,9],[1.6,.7,3]]) {
        const tail=trail.at(-1), gradient=ctx.createLinearGradient(tail.x,tail.y,point.x,point.y);
        gradient.addColorStop(0,'rgba(160,255,224,0)'); gradient.addColorStop(1,`rgba(225,255,245,${alpha})`);
        ctx.beginPath(); ctx.moveTo(tail.x,tail.y);
        for(let i=trail.length-2;i>=0;i--) ctx.lineTo(trail[i].x,trail[i].y);
        ctx.lineCap='round'; ctx.lineWidth=lineWidth; ctx.strokeStyle=gradient;
        ctx.shadowColor='rgba(185,255,227,.6)'; ctx.shadowBlur=blur; ctx.stroke();
      }
    }
    ctx.shadowBlur=0;
    const halo=ctx.createRadialGradient(point.x,point.y,0,point.x,point.y,radius*10);
    halo.addColorStop(0,'rgba(255,255,255,.9)'); halo.addColorStop(.08,'rgba(240,255,250,.7)');
    halo.addColorStop(.3,'rgba(183,255,224,.17)'); halo.addColorStop(1,'rgba(120,255,208,0)');
    ctx.fillStyle=halo; ctx.fillRect(point.x-radius*10,point.y-radius*10,radius*20,radius*20);
    // The scan is a light streak, not a filled panel-sized rectangle.
    const span=p>.61 ? bounds.width*.54*Math.sin(point.scan*Math.PI) : radius*4;
    if (span>1) {
      const beam=ctx.createLinearGradient(point.x-span,point.y,point.x+span,point.y);
      beam.addColorStop(0,'rgba(160,255,220,0)'); beam.addColorStop(.5,'rgba(245,255,250,.8)'); beam.addColorStop(1,'rgba(160,255,220,0)');
      ctx.strokeStyle=beam; ctx.lineWidth=1.2; ctx.shadowColor='#b2ffdb'; ctx.shadowBlur=10;
      ctx.beginPath();ctx.moveTo(point.x-span,point.y);ctx.lineTo(point.x+span,point.y);ctx.stroke();ctx.shadowBlur=0;
    }
    const core=ctx.createRadialGradient(point.x,point.y,0,point.x,point.y,radius);
    core.addColorStop(0,'rgba(255,255,255,1)');core.addColorStop(.2,'rgba(255,255,255,.96)');core.addColorStop(1,'rgba(220,255,240,0)');
    ctx.fillStyle=core;ctx.beginPath();ctx.arc(point.x,point.y,radius,0,Math.PI*2);ctx.fill();
    ctx.globalCompositeOperation='source-over';last={x:point.x,y:point.y,trail:trail.length,scan:point.scan};
  }
  return {draw,clear,diagnostics:()=>({frames,point:last,transparent:true})};
}
