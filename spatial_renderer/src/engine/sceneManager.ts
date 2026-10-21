import {Mesh,MeshBuilder,Scene,StandardMaterial,Color3,Vector3,Plane,Quaternion} from '@babylonjs/core';
import {Part,Snapshot} from './protocol';
import {ProgressiveBuilder} from './progressiveBuilder';
import {ParticleMaterializer} from './particleMaterializer';
import {AssetManager} from './assetManager';
export class SceneManager {
 meshes=new Map<string,Mesh>();private parts=new Map<string,Part>();private signatures=new Map<string,string>();
 builder=new ProgressiveBuilder();particles:ParticleMaterializer;private snapshot?:Snapshot;
 private assets:AssetManager;private loading=new Set<string>();
 constructor(private scene:Scene,private error:(text:string)=>void=console.error){this.particles=new ParticleMaterializer(scene);this.assets=new AssetManager(scene);}
 apply(snapshot:Snapshot){
  this.snapshot=snapshot;this.parts=new Map(snapshot.scene.parts.map(p=>[p.id,p]));
  for(const [id,mesh] of this.meshes)if(!this.parts.has(id)){if(mesh.metadata?.zaya_node)mesh.setEnabled(false);else if(!mesh.isDisposed())this.particles.dissolve(mesh);this.meshes.delete(id);this.signatures.delete(id);}
  const added:Part[]=[];
  for(const part of snapshot.scene.parts){if(this.meshes.has(part.id))this.update(part);else added.push(part);}
  this.builder.replace(added);this.view();
 }
 private create(part:Part){
  const g=part.geometry;let mesh:Mesh;
  if(g.primitive==='asset'){
   if(this.loading.has(part.id))return;this.loading.add(part.id);
   this.assets.obtain(part).then(value=>{this.loading.delete(part.id);if(!this.parts.has(part.id))return;
    this.meshes.set(part.id,value);this.signatures.set(part.id,JSON.stringify(g));value.material=new StandardMaterial(part.id+'-wrapper',this.scene);
    value.metadata.zaya_node.setEnabled(true);this.assets.show(part.id);this.update(this.parts.get(part.id)!);this.view();
   }).catch(error=>{this.loading.delete(part.id);this.error('Asset import failed: '+String(error));});return;
  }
  if(g.primitive==='sphere')mesh=MeshBuilder.CreateSphere(part.id,{diameter:g.radius*2,segments:g.segments},this.scene);
  else if(g.primitive==='torus')mesh=MeshBuilder.CreateTorus(part.id,{diameter:g.radius*2,thickness:Math.min(g.thickness,g.radius),tessellation:g.segments},this.scene);
  else if(g.primitive==='tube')mesh=MeshBuilder.CreateTube(part.id,{path:[new Vector3(0,-g.height/2,0),new Vector3(0,g.height/2,0)],radius:g.radius,tessellation:g.segments,sideOrientation:Mesh.DOUBLESIDE},this.scene);
  else if(['cylinder','cone','rod'].includes(g.primitive))mesh=MeshBuilder.CreateCylinder(part.id,{height:g.height,diameter:g.radius*2,diameterTop:g.primitive==='cone'?0:g.radius*2,tessellation:g.segments},this.scene);
  else mesh=MeshBuilder.CreateBox(part.id,{width:g.width,height:g.height,depth:g.depth},this.scene);
  mesh.metadata={part_id:part.id};mesh.material=new StandardMaterial(part.id+'-material',this.scene);
  this.meshes.set(part.id,mesh);this.signatures.set(part.id,JSON.stringify(g));
  this.update(part);mesh.computeWorldMatrix(true);this.particles.materialize(mesh);
 }
 private update(part:Part){
  let mesh=this.meshes.get(part.id)!;
  if(this.signatures.get(part.id)!==JSON.stringify(part.geometry)){if(mesh.metadata?.zaya_node)mesh.setEnabled(false);else mesh.dispose(false,true);this.meshes.delete(part.id);this.create(part);return;}
  mesh.position=Vector3.FromArray(part.transform.position);mesh.rotation=Vector3.FromArray(part.transform.rotation);mesh.scaling=Vector3.FromArray(part.transform.scale);
  mesh.rotationQuaternion=part.transform.rotation_quaternion?Quaternion.FromArray(part.transform.rotation_quaternion):null;
  const mat=mesh.material as StandardMaterial;mat.diffuseColor=Color3.FromHexString(part.material.color);mat.alpha=part.material.alpha;mat.wireframe=part.material.wireframe;
  mesh.setEnabled(part.visible);
 }
 private view(){
  const state=this.snapshot;if(!state)return;
  const selected=new Set(state.selected);
  for(const [id,mesh] of this.meshes){const part=this.parts.get(id)!;const material=mesh.material as StandardMaterial;
   mesh.parent=part.parent_id?this.meshes.get(part.parent_id)??null:null;
   const base=Vector3.FromArray(part.transform.position);let direction=base.length()>.01?base.normalize():new Vector3(1,1,0).normalize();
   mesh.position=Vector3.FromArray(part.transform.position).add(direction.scale(state.view.explode));
   const transparent=state.view.xray==='outer_transparent'&&part.layer==='outer'||state.view.xray==='selected_transparent'&&selected.has(id);
   material.alpha=transparent?.16:part.material.alpha;material.wireframe=state.view.xray==='wireframe'||part.material.wireframe;
   if(part.geometry.primitive==='asset')this.assets.style(part,transparent,material.wireframe,selected.has(id));
   mesh.setEnabled(part.visible&&!(state.view.xray==='internal_only'&&part.layer==='outer'));
   mesh.renderOutline=selected.has(id);mesh.outlineColor=new Color3(1,.4,.7);mesh.outlineWidth=.025;
  }
  const slice=state.view.slice;this.scene.clipPlane=slice?new Plane(slice.axis==='x'?1:0,slice.axis==='y'?1:0,slice.axis==='z'?1:0,slice.offset):null;
 }
 tick(ms:number){this.builder.tick(ms,p=>{if(this.parts.has(p.id)){this.create(this.parts.get(p.id)!);this.view();}});}
 select(id:string){if(this.snapshot){this.snapshot.selected=[id];this.view();}return this.parts.get(id);}
 selected(){return this.snapshot?.selected[0];}
 revision(){return this.snapshot?.scene.revision??0;}
 restore(id:string){const part=this.parts.get(id);if(part&&this.meshes.has(id)){this.update(part);this.view();}}
}
