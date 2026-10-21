import {Engine,WebGPUEngine,Scene,ArcRotateCamera,Vector3,HemisphericLight,Color4,AbstractEngine} from '@babylonjs/core';
export async function createRenderer(canvas:HTMLCanvasElement){
 let engine:AbstractEngine;
 try {if(!await WebGPUEngine.IsSupportedAsync)throw Error('WebGPU unavailable');const gpu=new WebGPUEngine(canvas);await gpu.initAsync();engine=gpu;}
 catch {engine=new Engine(canvas,true,{preserveDrawingBuffer:false,stencil:true});}
 const scene=new Scene(engine);scene.clearColor=new Color4(.07,.055,.09,1);
 const camera=new ArcRotateCamera('orbit',-Math.PI/2,Math.PI/2.7,10,Vector3.Zero(),scene);
 camera.attachControl(canvas,true);camera.lowerRadiusLimit=.4;camera.upperRadiusLimit=100;
 new HemisphericLight('light',new Vector3(1,2,-1),scene);
 window.addEventListener('resize',()=>engine.resize());
 return {engine,scene,camera};
}
