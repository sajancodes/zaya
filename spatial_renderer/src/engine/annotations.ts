import {Scene,Vector3,Matrix,Mesh} from '@babylonjs/core';
import {Annotation} from './protocol';
export class Annotations {
 private entries=new Map<string,{data:Annotation;element:HTMLDivElement}>();
 constructor(private scene:Scene,private meshes:Map<string,Mesh>){}
 apply(values:Annotation[]){
  const ids=new Set(values.map(a=>a.id));for(const [id,value] of this.entries)if(!ids.has(id)){value.element.remove();this.entries.delete(id);}
  for(const data of values){let entry=this.entries.get(data.id);if(!entry){const element=document.createElement('div');element.style.cssText='position:absolute;top:0;left:0;pointer-events:none;background:#302335d9;border:1px solid #a77894;border-radius:6px;padding:4px 8px;max-width:240px;font:13px system-ui;color:#ffe0ee';document.body.append(element);entry={data,element};this.entries.set(data.id,entry);}entry.data=data;entry.element.textContent=data.text;}
 }
 tick(){const camera=this.scene.activeCamera;if(!camera)return;const engine=this.scene.getEngine(),canvas=engine.getRenderingCanvas();if(!canvas)return;
  for(const {data,element} of this.entries.values()){const mesh=data.part_id?this.meshes.get(data.part_id):undefined;if(data.part_id&&(!mesh||!mesh.isEnabled())){element.hidden=true;continue;}const world=(mesh?.getAbsolutePosition()??Vector3.Zero()).add(Vector3.FromArray(data.position));const point=Vector3.Project(world,Matrix.Identity(),this.scene.getTransformMatrix(),camera.viewport.toGlobal(engine.getRenderWidth(),engine.getRenderHeight()));element.hidden=point.z<0||point.z>1;if(!element.hidden)element.style.transform=`translate(${point.x*canvas.clientWidth/engine.getRenderWidth()}px,${point.y*canvas.clientHeight/engine.getRenderHeight()}px)`;}
 }
}
