import {Mesh,PointsCloudSystem,Vector3,Color4,Scene,VertexBuffer,CloudPoint} from '@babylonjs/core';
export class ParticleMaterializer {
 private active=new Set<PointsCloudSystem>();
 budget=100;
 constructor(private scene:Scene){}
 materialize(mesh:Mesh){this.effect(mesh,false);}
 dissolve(mesh:Mesh){mesh.isPickable=false;this.effect(mesh,true);}
 private effect(mesh:Mesh,dissolving:boolean){
  if(this.active.size>=8||this.budget===0){if(dissolving)mesh.dispose(false,true);return;}
  const cloud=new PointsCloudSystem('sand',2,this.scene);this.active.add(cloud);
  const vertices=mesh.getVerticesData(VertexBuffer.PositionKind)||[0,0,0];const targets:Vector3[]=[];
  const originalVisibility=mesh.visibility;
  cloud.addPoints(this.budget,(p:CloudPoint)=>{const i=Math.floor(Math.random()*(vertices.length/3))*3;const local=new Vector3(vertices[i],vertices[i+1],vertices[i+2]);targets[p.idx]=local;const target=Vector3.TransformCoordinates(local,mesh.getWorldMatrix());p.position=dissolving?target:target.add(new Vector3((Math.random()-.5)*2,(Math.random()-.5)*2,(Math.random()-.5)*2));p.color=new Color4(1,.72,.84,1);});
  let age=0;const observer=this.scene.onBeforeRenderObservable.add(()=>{age+=this.scene.getEngine().getDeltaTime()/1000;if(age>.55||mesh.isDisposed()){this.scene.onBeforeRenderObservable.remove(observer);cloud.dispose();this.active.delete(cloud);if(dissolving&&!mesh.isDisposed())mesh.dispose(false,true);else if(!mesh.isDisposed())mesh.visibility=originalVisibility;return;}mesh.visibility=originalVisibility*(dissolving?1-age/.55:age/.55);for(const p of cloud.particles){const target=Vector3.TransformCoordinates(targets[p.idx],mesh.getWorldMatrix());p.position=dissolving?p.position.add(new Vector3(.01*Math.sin(p.idx),.015,.01*Math.cos(p.idx))):Vector3.Lerp(p.position,target,.16);}cloud.setParticles();});
  cloud.buildMeshAsync().catch(()=>{this.scene.onBeforeRenderObservable.remove(observer);this.active.delete(cloud);cloud.dispose();});
 }
}
