export class NeuralLifecycle {
  constructor(){this.progress=0;this.target=0;this.elapsed=0;this.requestId=null;this.items=[];this.depth='deep';this.hold=0;this.wait=0;this.awaitingTopic=false;this.outcome=null;}
  update(payload){
    if(!payload||typeof payload!=='object')return;
    if(payload.pending){this.requestId=payload.requestId;this.lastRequestId=payload.requestId;this.items=[];this.awaitingTopic=false;this.outcome=null;this.target=.12;this.elapsed=0;this.wait=0;return;}
    if(payload.requestId!==this.requestId)return;
    this.wait=0;
    this.items=Array.isArray(payload.items)?payload.items.slice(0,3).filter(item=>item&&typeof item.id==='string'&&typeof item.detail==='string'):[];
    this.awaitingTopic=payload.active===true&&payload.awaitingTopic===true;
    this.outcome=payload.active===true&&['empty','unavailable'].includes(payload.outcome)?payload.outcome:null;
    if(this.awaitingTopic)this.items=[];
    this.depth=payload.depth||'deep';this.target=payload.active&&(this.items.length||this.awaitingTopic||this.outcome)?1:0;this.hold=0;
  }
  cancel(){this.target=0;this.items=[];this.requestId=null;this.wait=0;this.awaitingTopic=false;this.outcome=null;}
  step(dt,{speaking=false,reduced=false}={}){
    dt=Math.max(0,Math.min(.5,Number.isFinite(dt)?dt:0));
    if(this.target===.12){this.wait+=dt;if(this.wait>20)this.cancel();}
    const duration=this.target===0?1.4:this.depth==='quick'?2.4:this.depth==='context'?3.6:4.8;
    if(reduced)this.progress=this.target===1?1:0;
    else this.progress=Math.max(0,Math.min(1,this.progress+Math.sign(this.target-this.progress)*Math.min(Math.abs(this.target-this.progress),dt/duration)));
    if(this.progress===1&&this.target===1){this.hold=speaking?0:this.hold+dt;if(this.hold>(this.awaitingTopic?30:this.outcome?6:4))this.cancel();}
    if(this.target===0&&this.progress===0){this.items=[];this.requestId=null;this.awaitingTopic=false;}
    return this.progress;
  }
  get active(){return this.progress>0||this.target>0;}
}
