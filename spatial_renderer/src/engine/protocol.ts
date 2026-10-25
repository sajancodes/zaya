export interface Part {id:string;name:string;kind:string;parent_id:string|null;layer:string;visible:boolean;metadata:Record<string,string>;transform:{position:number[];rotation:number[];scale:number[];rotation_quaternion?:number[]|null};geometry:{primitive:string;width:number;height:number;depth:number;radius:number;thickness:number;segments:number;asset_id?:string;node_index?:number};material:{color:string;alpha:number;wireframe:boolean}}
export interface Annotation {id:string;text:string;part_id:string|null;position:number[]}
export interface Snapshot {scene:{name:string;accuracy:string;revision:number;parts:Part[];annotations?:Annotation[]};selected:string[];view:{explode:number;explode_parts?:Record<string,number>;xray:string;slice:{axis?:string;normal?:number[];offset:number}|null};camera?:{alpha:number;beta:number;radius:number;target:number[]};building?:boolean}
export interface HandSample {id:string;pose:string;x:number;y:number;palm:number[];wrist:number}
export interface HandFrame {hands:HandSample[];pokes:string[];selection_only:boolean;gestures?:string[]}
export interface Packet {version:number;type:string;session_id:string;sequence:number;payload:unknown}
export function valid(raw:unknown): raw is Packet {
 const p=raw as Packet;return !!p&&p.version===1&&typeof p.session_id==='string'&&Number.isSafeInteger(p.sequence)&&!!p.payload;
}
