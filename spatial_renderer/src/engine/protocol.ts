export interface Part {id:string;name:string;kind:string;parent_id:string|null;layer:string;visible:boolean;transform:{position:number[];rotation:number[];scale:number[]};geometry:{primitive:string;width:number;height:number;depth:number;radius:number;thickness:number;segments:number};material:{color:string;alpha:number;wireframe:boolean}}
export interface Snapshot {scene:{name:string;accuracy:string;revision:number;parts:Part[]};selected:string[];view:{explode:number;xray:string;slice:{axis:string;offset:number}|null}}
export interface Packet {version:number;type:string;session_id:string;sequence:number;payload:Snapshot}
export function valid(raw:unknown): raw is Packet {
 const p=raw as Packet;return !!p&&p.version===1&&typeof p.session_id==='string'&&Number.isSafeInteger(p.sequence)&&!!p.payload;
}
