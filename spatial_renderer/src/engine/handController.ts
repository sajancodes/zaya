import {Scene,ArcRotateCamera,Vector3,Matrix,Plane,Mesh} from '@babylonjs/core';
import {HandFrame,HandSample} from './protocol';
import {SceneManager} from './sceneManager';
import {Connection} from './connection';

export class HandController {
 private previous?:HandFrame;private at=0;private twoDistance=0;private pullDistance=0;private lastExplode=0;
 private grab?:{id:string;mesh:Mesh;plane:Plane;offset:Vector3;wrist:number;rotation:Vector3;revision:number};
 constructor(private scene:Scene,private camera:ArcRotateCamera,private manager:SceneManager,private connection:Connection,private label:(text:string)=>void){}
 private ray(hand:HandSample){const engine=this.scene.getEngine();return this.scene.createPickingRay(hand.x*engine.getRenderWidth(),hand.y*engine.getRenderHeight(),Matrix.Identity(),this.camera,false);}
 private pick(hand:HandSample){const pick=this.scene.pickWithRay(this.ray(hand),mesh=>typeof mesh.metadata?.part_id==='string'&&mesh.isPickable);return pick?.pickedMesh?.metadata?.part_id as string|undefined;}
 private select(id:string){const part=this.manager.select(id);this.label(part?.name??id);this.connection.send('selection.changed',{ids:[id]});}
 cancel(){if(this.grab){this.manager.restore(this.grab.id);this.grab=undefined;}this.previous=undefined;this.twoDistance=this.pullDistance=0;}
 tick(){if(this.at&&Date.now()-this.at>250)this.cancel();}
 update(frame:HandFrame){
  this.at=Date.now();const hand=frame.hands[0];
  if(!hand){this.cancel();return;}
  if(frame.pokes.includes(hand.id)){const id=this.pick(hand);if(id)this.select(id);}
  if(frame.selection_only){this.previous=frame;return;}
  if(hand.pose==='FIST'){this.cancel();return;}
  if(this.grab){
   if(this.grab.mesh.isDisposed()||this.manager.revision()!==this.grab.revision){this.cancel();return;}
   if(hand.pose==='PINCH'){
    const distance=this.ray(hand).intersectsPlane(this.grab.plane);
    if(distance!==null){const world=this.ray(hand).origin.add(this.ray(hand).direction.scale(distance)).add(this.grab.offset);this.grab.mesh.position=this.grab.mesh.parent?Vector3.TransformCoordinates(world,Matrix.Invert(this.grab.mesh.parent.getWorldMatrix())):world;}
    const delta=Math.atan2(Math.sin(hand.wrist-this.grab.wrist),Math.cos(hand.wrist-this.grab.wrist));
    this.grab.mesh.rotation=this.grab.rotation.add(new Vector3(0,0,delta));
   }else if(hand.pose!=='NONE'){
    const grab=this.grab;this.grab=undefined;
    this.connection.send('part.manipulated',{part_id:grab.id,position:grab.mesh.position.asArray(),rotation:grab.mesh.rotation.asArray(),revision:grab.revision});
   }
  }else if(hand.pose==='PINCH'&&frame.hands.length===1){
   const id=this.manager.selected();const mesh=id?this.manager.meshes.get(id):undefined;
   if(id&&mesh){if(mesh.rotationQuaternion){mesh.rotation=mesh.rotationQuaternion.toEulerAngles();mesh.rotationQuaternion=null;}const plane=Plane.FromPositionAndNormal(mesh.getAbsolutePosition(),this.camera.getForwardRay().direction);const ray=this.ray(hand),distance=ray.intersectsPlane(plane);if(distance!==null)this.grab={id,mesh,plane,offset:mesh.getAbsolutePosition().subtract(ray.origin.add(ray.direction.scale(distance))),wrist:hand.wrist,rotation:mesh.rotation.clone(),revision:this.manager.revision()};}
  }
  const previous=this.previous?.hands.find(old=>old.id===hand.id);
  if(frame.hands.length===2){
   const second=frame.hands[1];const distance=Vector3.FromArray(hand.palm).subtract(Vector3.FromArray(second.palm)).length();
   if(hand.pose==='OPEN_PALM'&&second.pose==='OPEN_PALM'){
    if(this.twoDistance>.02&&distance>.02)this.camera.radius=Math.min(100,Math.max(.4,this.camera.radius*this.twoDistance/distance));
    this.twoDistance=distance;this.pullDistance=0;
   }else if(hand.pose==='PINCH'&&second.pose==='PINCH'){
    if(!this.pullDistance)this.pullDistance=distance;
    if(distance-this.pullDistance>.15&&Date.now()-this.lastExplode>1000){this.connection.send('view.changed',{explode:1.5});this.lastExplode=Date.now();this.pullDistance=distance;}
   }
  }else{
   this.twoDistance=this.pullDistance=0;
   if(!this.grab&&previous&&hand.pose==='OPEN_PALM'&&previous.pose==='OPEN_PALM'){
    this.camera.alpha-=(hand.palm[0]-previous.palm[0])*4;
    this.camera.beta=Math.min(2.9,Math.max(.2,this.camera.beta+(hand.palm[1]-previous.palm[1])*3));
   }
  }
  this.previous=frame;
 }
}
