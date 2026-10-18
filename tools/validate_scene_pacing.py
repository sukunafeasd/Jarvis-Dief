"""Local software-WebGL pacing probe; no accounts, microphone or providers."""
import asyncio,json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'tests'),str(ROOT)]
from test_refresh_visual import RefreshVisualTests

async def check():
    fixture=RefreshVisualTests();await fixture.asyncSetUp()
    output=Path(tempfile.mkdtemp(prefix='dief-scene-pacing-'))
    records={}
    try:
        for document,diagnostic,update in [('index.html','hologramDiagnostics','updateEnvironment'),('space.html','spaceDiagnostics','updateCore')]:
            page=fixture.page
            await page.goto(fixture.url+'/'+document)
            await page.wait_for_function('document.body.dataset.ready==="true"',timeout=60000)
            result=await page.evaluate('''async ([diagnostic,update])=>{
                window[update]({staging:false,mode:'assistant',entrance:{at:Date.now(),duration:4300}});
                return await new Promise(resolve=>{
                    const start=performance.now(),samples=[];let last=window[diagnostic]().framesRendered??window[diagnostic]().frames,previous=start;
                    function frame(now){
                        const state=window[diagnostic](),count=state.framesRendered??state.frames;
                        if(count!==last){samples.push(now-previous);previous=now;last=count;}
                        if(now-start<2000){requestAnimationFrame(frame);return;}
                        samples.sort((a,b)=>a-b);
                        resolve({frames:samples.length,median_ms:samples[Math.floor(samples.length*.5)],p95_ms:samples[Math.floor(samples.length*.95)],max_ms:Math.max(...samples),state});
                    }
                    requestAnimationFrame(frame);
                });
            }''',[diagnostic,update])
            await page.screenshot(path=str(output/(document+'.png')))
            records[document]=result
        report={'records':records,'errors':fixture.errors,'output':str(output),'renderer':'headless Edge / software WebGL; not hardware performance'}
        (output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        return report
    finally:await fixture.asyncTearDown()

if __name__=='__main__':print(json.dumps(asyncio.run(check())),flush=True)
