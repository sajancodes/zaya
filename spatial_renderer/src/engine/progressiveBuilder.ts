import {Part} from './protocol';
export class ProgressiveBuilder {
 private pending=new Map<string,Part>();private elapsed=0;
 replace(parts:Part[]){this.pending=new Map(parts.map(p=>[p.id,p]));}
 tick(ms:number,add:(part:Part)=>void){this.elapsed+=ms;if(this.elapsed<45)return;this.elapsed=0;const entry=this.pending.entries().next().value;if(entry){this.pending.delete(entry[0]);add(entry[1]);}}
 get remaining(){return this.pending.size;}
}
