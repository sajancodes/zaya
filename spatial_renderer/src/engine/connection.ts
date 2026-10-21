import {Packet,valid} from './protocol';
export class Connection {
 private token=location.hash.slice(1)||sessionStorage.getItem('zaya-spatial-token')||'';private socket?:WebSocket;private session='';private last=0;private outgoing=0;private stopped=false;
 constructor(private receive:(packet:Packet)=>void,private status:(text:string)=>void){sessionStorage.setItem('zaya-spatial-token',this.token);history.replaceState(null,'',location.pathname);this.connect();}
 private connect(){
  if(this.stopped)return;
  const ws=new WebSocket(`ws://${location.host}/ws?token=${encodeURIComponent(this.token)}`);this.socket=ws;
  ws.onopen=()=>{this.last=0;this.outgoing=0;this.status('Connected · local rendering');};
  ws.onmessage=event=>{try{if(typeof event.data!=='string'||event.data.length>512000)throw Error('Oversized packet');const p:unknown=JSON.parse(event.data);if(!valid(p))throw Error('Malformed packet');if(this.session&&p.session_id!==this.session&&p.type!=='scene.create')return;this.session=p.session_id;if(p.sequence<=this.last)return;this.last=p.sequence;this.receive(p);}catch{this.status('Invalid renderer message ignored');}};
  ws.onclose=()=>{this.status('Disconnected · scene preserved · retrying');setTimeout(()=>this.connect(),1500);};
 }
 send(type:string,payload:unknown){if(this.socket?.readyState===WebSocket.OPEN&&this.session)this.socket.send(JSON.stringify({version:1,type,session_id:this.session,sequence:++this.outgoing,payload}));}
 stop(){this.stopped=true;this.socket?.close();}
}
