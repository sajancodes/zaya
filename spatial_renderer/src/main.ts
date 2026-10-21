import {createRenderer} from './engine/renderer';
import {SceneManager} from './engine/sceneManager';
import {Connection} from './engine/connection';
import {PerformanceManager} from './engine/performanceManager';
import {HandController} from './engine/handController';
import {Snapshot,HandFrame} from './engine/protocol';
const status=document.querySelector('#status')!;const selection=document.querySelector('#selection')!;
async function main(){
 const {engine,scene,camera}=await createRenderer(document.querySelector('canvas')!);
 const manager=new SceneManager(scene);const performance=new PerformanceManager(engine,manager.particles);
 let hands:HandController;
 const connection=new Connection(packet=>{if(packet.type.startsWith('scene.')){const snapshot=packet.payload as Snapshot;manager.apply(snapshot);status.textContent=`${snapshot.scene.name} · ${snapshot.scene.accuracy} · revision ${snapshot.scene.revision}`;}else if(packet.type==='interaction.frame')hands?.update(packet.payload as HandFrame);},text=>status.textContent=text);
 hands=new HandController(scene,camera,manager,connection,text=>selection.textContent=text);
 let xray=false,exploded=false,sliced=false;
 document.querySelector('#xray')!.addEventListener('click',()=>{xray=!xray;connection.send('view.changed',{xray:xray?'outer_transparent':'normal'});});
 document.querySelector('#explode')!.addEventListener('click',()=>{exploded=!exploded;connection.send('view.changed',{explode:exploded?1.5:0});});
 document.querySelector('#slice')!.addEventListener('click',()=>{sliced=!sliced;connection.send('view.changed',{slice:sliced?{axis:'x',offset:0}:null});});
 document.querySelector('#reset')!.addEventListener('click',()=>{xray=exploded=sliced=false;connection.send('view.changed',{explode:0,xray:'normal',slice:null});camera.alpha=-Math.PI/2;camera.beta=Math.PI/2.7;camera.radius=10;});
 scene.onPointerDown=(_event,pick)=>{if(_event.target!==document.querySelector('canvas'))return;const id=pick.pickedMesh?.metadata?.part_id;if(typeof id==='string'){const part=manager.select(id);selection.textContent=part?.name??id;connection.send('selection.changed',{ids:[id]});}};
 engine.runRenderLoop(()=>{hands.tick();manager.tick(engine.getDeltaTime());scene.render();performance.tick(Date.now());});
 window.addEventListener('beforeunload',()=>connection.stop());
}
main().catch(error=>{document.querySelector('#error')!.textContent='Renderer unavailable: '+String(error);});
