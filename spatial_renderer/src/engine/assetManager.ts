import {Scene,SceneLoader,Mesh,AbstractMesh,Node,Quaternion,Vector3,Material} from '@babylonjs/core';
import '@babylonjs/loaders/glTF';
import {Part} from './protocol';

export class AssetManager {
 private bundles=new Map<string,Promise<Map<string,Mesh>>>();private leaves=new Map<string,AbstractMesh[]>();
 private originals=new Map<Material,{alpha:number;transparency:number|null}>();
 constructor(private scene:Scene){}
 async obtain(part:Part):Promise<Mesh>{
  const id=part.geometry.asset_id!;
  if(!this.bundles.has(id)){
   const file=part.metadata.asset_file;if(file!=='model.glb'&&file!=='model.gltf')throw Error('Invalid asset manifest');
   this.bundles.set(id,SceneLoader.LoadAssetContainerAsync(`/assets/${id}/`,file,this.scene).then(container=>{
    container.addAllToScene();const result=new Map<string,Mesh>();
    const nodes=[...container.transformNodes,...container.meshes];
    for(const mesh of container.meshes){
     let node:Node|null=mesh;let owner:string|undefined;
     while(node){owner=node.metadata?.gltf?.extras?.zaya_part_id;if(owner)break;node=node.parent;}
     if(owner){mesh.metadata={...mesh.metadata,part_id:owner};const owned=this.leaves.get(owner)||[];owned.push(mesh);this.leaves.set(owner,owned);
      if(mesh.material){mesh.material=mesh.material.clone(mesh.material.name+'-'+mesh.uniqueId);if(mesh.material)this.originals.set(mesh.material,{alpha:mesh.material.alpha,transparency:mesh.material.transparencyMode});}}
    }
    for(const node of nodes){
     const owner=node.metadata?.gltf?.extras?.zaya_part_id;if(typeof owner!=='string'||result.has(owner))continue;
     const wrapper=new Mesh(owner,this.scene);wrapper.parent=node.parent;wrapper.position=node.position.clone();wrapper.scaling=node.scaling.clone();wrapper.rotation=node.rotation.clone();wrapper.rotationQuaternion=node.rotationQuaternion?.clone()??null;
     node.parent=wrapper;node.position=Vector3.Zero();node.scaling=Vector3.One();node.rotation=Vector3.Zero();node.rotationQuaternion=Quaternion.Identity();node.setEnabled(false);
     wrapper.metadata={part_id:owner,zaya_node:node};result.set(owner,wrapper);
    }
    return result;
   }));
  }
  const map=await this.bundles.get(id)!;const mesh=map.get(part.id);if(!mesh)throw Error('Asset semantic node was not loaded');return mesh;
 }
 show(id:string){for(const mesh of this.leaves.get(id)||[]){mesh.setEnabled(true);} }
 style(part:Part,transparent:boolean,wireframe:boolean,selected:boolean){
  for(const mesh of this.leaves.get(part.id)||[]){const material=mesh.material;if(!material)continue;const original=this.originals.get(material);material.alpha=transparent?.16:(original?.alpha??1)*part.material.alpha;material.transparencyMode=transparent?Material.MATERIAL_ALPHABLEND:original?.transparency??null;material.wireframe=wireframe;mesh.renderOutline=selected;}
 }
}
