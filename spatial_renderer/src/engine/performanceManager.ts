import {AbstractEngine} from '@babylonjs/core';
import {ParticleMaterializer} from './particleMaterializer';
export class PerformanceManager {
 private low=0;private last=0;
 constructor(private engine:AbstractEngine,private particles:ParticleMaterializer){}
 tick(time:number){if(time-this.last<1000)return;this.last=time;const fps=this.engine.getFps();this.low=fps<30?this.low+1:Math.max(0,this.low-1);if(this.low>=3){this.particles.budget=30;this.engine.setHardwareScalingLevel(1.5);}if(this.low>=8){this.particles.budget=0;this.engine.setHardwareScalingLevel(2);}}
}
