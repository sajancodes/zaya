import threading
import uuid
import math
import time
import json
from pathlib import Path
from .schema import SpatialScene
from .scene_patcher import apply_patch
from .scene_graph import part_context
from .spatial_protocol import envelope


class SpatialSession:
    def __init__(self,path=None):
        self.lock=threading.RLock()
        self.session_id=uuid.uuid4().hex
        self.scene=SpatialScene(scene_id=uuid.uuid4().hex,name='Zaya workspace')
        self.selected_part_ids=[]
        self.undo_stack,self.redo_stack=[],[]
        self.sequence=0
        self.renderer_connected=False
        self.listeners=set()
        self.view={'explode':0.,'explode_parts':{},'xray':'normal','slice':None}
        self.camera_state={'alpha':-math.pi/2,'beta':math.pi/2.7,'radius':10.,'target':[0.,0.,0.]}
        self.renderer_metrics={}
        self.path=Path(path) if path else None
        self.persistence_error=''
        self.saved_at=0
        self.build_backup=None
        if self.path and self.path.is_file():
            self.restore()

    def publish(self,kind,payload):
        with self.lock:
            self.sequence+=1
            packet=envelope(kind,self.session_id,self.sequence,payload)
            for listener in tuple(self.listeners):
                try:
                    listener(packet)
                except Exception:
                    self.listeners.discard(listener)
                    self.renderer_connected=bool(self.listeners)
            return packet

    def snapshot(self):
        with self.lock:
            return {'scene':self.scene.model_dump(mode='json'),'selected':list(self.selected_part_ids),'view':dict(self.view),'camera':dict(self.camera_state),'building':self.build_backup is not None}

    def replace(self,scene):
        validated=SpatialScene.model_validate(scene)
        with self.lock:
            if self.build_backup is not None:raise ValueError('A streamed scene is still being built.')
            # Revisions remain monotonic, including scene changes and undo.
            validated=validated.model_copy(update={'revision':self.scene.revision+1})
            self._remember();self.scene=validated;self.selected_part_ids=[]
            valid={p.id for p in validated.parts}
            self.view['explode_parts']={key:value for key,value in self.view.get('explode_parts',{}).items() if key in valid}
            self.publish('scene.create',self.snapshot())
            self.save()

    def _remember(self):
        self.undo_stack.append(self.scene.model_copy(deep=True))
        self.undo_stack=self.undo_stack[-20:];self.redo_stack.clear()

    def patch(self,operations,expected_revision):
        with self.lock:
            if self.build_backup is not None:raise ValueError('Wait for the current streamed build before modifying parts.')
            candidate=apply_patch(self.scene,operations,expected_revision)
            self._remember();self.scene=candidate
            valid={p.id for p in candidate.parts}
            self.selected_part_ids=[p for p in self.selected_part_ids if p in valid]
            self.view['explode_parts']={key:value for key,value in self.view.get('explode_parts',{}).items() if key in valid}
            self.publish('scene.patch',self.snapshot())
            self.save()

    def history(self,redo=False):
        with self.lock:
            if self.build_backup is not None:raise ValueError('Wait for the current streamed build before undoing.')
            source,target=(self.redo_stack,self.undo_stack) if redo else (self.undo_stack,self.redo_stack)
            if not source:
                raise ValueError('No history in that direction.')
            target.append(self.scene.model_copy(deep=True))
            self.scene=source.pop().model_copy(update={'revision':self.scene.revision+1})
            self.selected_part_ids=[]
            valid={p.id for p in self.scene.parts}
            self.view['explode_parts']={key:value for key,value in self.view.get('explode_parts',{}).items() if key in valid}
            self.publish('scene.patch',self.snapshot())
            self.save()

    def select(self,ids):
        with self.lock:
            if not isinstance(ids,list) or len(ids)>20 or any(not isinstance(pid,str) for pid in ids):
                raise ValueError('Invalid selection.')
            if not set(ids)<={p.id for p in self.scene.parts}:
                raise ValueError('Selection references an unknown part.')
            self.selected_part_ids=list(dict.fromkeys(ids))
            self.save()

    def context(self):
        with self.lock:
            return part_context(self.scene,self.selected_part_ids)

    def set_view(self,change):
        if not isinstance(change,dict) or set(change)-{'explode','explode_parts','xray','slice'}:
            raise ValueError('Unknown view property.')
        if 'explode' in change and 'explode_parts' not in change:change={**change,'explode_parts':{}}
        value={**self.view,**change}
        amount=value['explode']
        if type(amount) not in (int,float) or not math.isfinite(amount) or not 0<=amount<=5:
            raise ValueError('Invalid explosion amount.')
        if value['xray'] not in ('normal','outer_transparent','selected_transparent','internal_only','wireframe'):
            raise ValueError('Unknown X-ray mode.')
        overrides=value.get('explode_parts',{})
        if not isinstance(overrides,dict) or not set(overrides)<={p.id for p in self.scene.parts} or any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=5 for v in overrides.values()):
            raise ValueError('Invalid part explosion offsets.')
        plane=value['slice']
        if plane is not None:
            if not isinstance(plane,dict) or type(plane.get('offset')) not in (int,float) or not math.isfinite(plane['offset']) or abs(plane['offset'])>100:
                raise ValueError('Invalid clipping plane.')
            if set(plane)=={'normal','offset'}:
                normal=plane['normal']
                if not isinstance(normal,list) or len(normal)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>1000 for v in normal):raise ValueError('Invalid plane normal.')
                length=math.hypot(*normal)
                if length<.001 or abs(plane['offset']/length)>100:raise ValueError('Invalid plane magnitude.')
                plane={'normal':[v/length for v in normal],'offset':plane['offset']/length};change={**change,'slice':plane}
            elif set(plane)!={'axis','offset'} or plane['axis'] not in ('x','y','z'):
                raise ValueError('Invalid clipping axis.')
        with self.lock:
            self.view={**self.view,**change};self.publish('scene.patch',self.snapshot())
            self.save()

    def manipulate(self,payload):
        if not isinstance(payload,dict) or set(payload)!={'part_id','position','rotation','revision'}:
            raise ValueError('Invalid hand manipulation payload.')
        with self.lock:
            if payload['part_id'] not in self.selected_part_ids:
                raise ValueError('Only the selected part may be manipulated.')
            self.patch([{'op':'update','part_id':payload['part_id'],'path':'transform.rotation_quaternion','value':None},
                        {'op':'update','part_id':payload['part_id'],'path':'transform.position','value':payload['position']},
                        {'op':'update','part_id':payload['part_id'],'path':'transform.rotation','value':payload['rotation']}],payload['revision'])

    def metrics(self,payload):
        if not isinstance(payload,dict) or set(payload)-{'fps','camera','error'}:
            raise ValueError('Invalid renderer telemetry.')
        fps=payload.get('fps',0.)
        if type(fps) not in (int,float) or not math.isfinite(fps) or not 0<=fps<=1000:
            raise ValueError('Invalid renderer FPS.')
        camera=payload.get('camera')
        if camera is not None:
            if not isinstance(camera,dict) or set(camera)!={'alpha','beta','radius','target'}:
                raise ValueError('Invalid camera state.')
            values=[camera['alpha'],camera['beta'],camera['radius']]
            if not isinstance(camera['target'],list) or len(camera['target'])!=3:
                raise ValueError('Invalid camera target.')
            values+=camera['target']
            if any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>1000 for v in values) or not .1<=camera['radius']<=100:
                raise ValueError('Camera exceeds limits.')
        with self.lock:
            if camera is not None:self.camera_state=camera
            self.renderer_metrics={'fps':fps,'error':str(payload.get('error') or '')[:300],'received_at':time.time()}
            if time.monotonic()-self.saved_at>10:self.save()

    def save(self):
        if self.path is None or self.build_backup is not None:return
        with self.lock:
            try:
                value={**self.snapshot(),'version':1,'undo':[s.model_dump(mode='json') for s in self.undo_stack[-20:]],
                       'redo':[s.model_dump(mode='json') for s in self.redo_stack[-20:]]}
                encoded=json.dumps(value,allow_nan=False,separators=(',',':'))
                if len(encoded.encode())>12_000_000:raise ValueError('Saved workspace exceeds limits.')
                self.path.parent.mkdir(parents=True,exist_ok=True)
                temporary=self.path.with_suffix('.tmp');temporary.write_text(encoded,encoding='utf-8');temporary.replace(self.path)
                self.saved_at=time.monotonic();self.persistence_error=''
            except (OSError,ValueError) as error:
                self.persistence_error=f'Workspace persistence failed ({type(error).__name__}).'

    def restore(self):
        try:
            if self.path.stat().st_size>12_000_000:raise ValueError('Saved workspace exceeds limits.')
            value=json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(value,dict):raise ValueError('Invalid saved workspace.')
            if value.get('version')!=1:raise ValueError('Unknown workspace version.')
            scene=SpatialScene.model_validate(value['scene'])
            undo=[SpatialScene.model_validate(s) for s in value.get('undo',[])[:20]]
            redo=[SpatialScene.model_validate(s) for s in value.get('redo',[])[:20]]
            # Validate all incoming cache state before replacing the live scene.
            probe=SpatialSession();probe.scene=scene
            probe.select(value.get('selected',[]));probe.set_view(value.get('view',{}))
            probe.metrics({'camera':value.get('camera',self.camera_state),'fps':0})
            self.scene,self.undo_stack,self.redo_stack=scene,undo,redo
            self.selected_part_ids=probe.selected_part_ids;self.view=probe.view;self.camera_state=probe.camera_state
        except (OSError,ValueError,TypeError,KeyError) as error:
            self.persistence_error=f'Workspace recovery failed ({type(error).__name__}); original cache retained.'

    def clear_history(self):
        with self.lock:
            self.undo_stack.clear();self.redo_stack.clear();self.save()

    def referenced_assets(self):
        with self.lock:
            previous=[self.build_backup[0]] if self.build_backup is not None else []
            return {p.geometry.asset_id for scene in [self.scene,*self.undo_stack,*self.redo_stack,*previous] for p in scene.parts if p.geometry.asset_id}

    def begin_build(self,name):
        with self.lock:
            if self.build_backup is not None:raise ValueError('Another spatial build is already running.')
            self.build_backup=(self.scene,self.selected_part_ids,self.view)
            self.scene=SpatialScene(scene_id=uuid.uuid4().hex,name=name[:160] or 'Generated scene',revision=self.scene.revision+1)
            self.selected_part_ids=[];self.view={'explode':0.,'explode_parts':{},'xray':'normal','slice':None}
            self.publish('scene.create',self.snapshot())
            return self.scene.scene_id

    def add_build_part(self,token,part):
        with self.lock:
            if self.build_backup is None or self.scene.scene_id!=token:raise ValueError('Stale build token.')
            self.scene=apply_patch(self.scene,[{'op':'add','value':part}],self.scene.revision)
            self.publish('scene.patch',self.snapshot())

    def finish_build(self,token,relationships):
        with self.lock:
            if self.build_backup is None or self.scene.scene_id!=token:raise ValueError('Stale build token.')
            value=self.scene.model_dump();value['relationships']=relationships;value['revision']+=1
            candidate=SpatialScene.model_validate(value)
            self.undo_stack.append(self.build_backup[0]);self.undo_stack=self.undo_stack[-20:];self.redo_stack.clear()
            self.scene=candidate;self.build_backup=None
            self.publish('scene.patch',self.snapshot());self.save()

    def abort_build(self,token):
        with self.lock:
            if self.build_backup is None or self.scene.scene_id!=token:return
            revision=self.scene.revision+1
            self.scene,self.selected_part_ids,self.view=self.build_backup;self.build_backup=None
            self.scene=self.scene.model_copy(update={'revision':revision})
            self.publish('scene.create',self.snapshot())


session=SpatialSession(Path(__file__).resolve().parents[2]/'memory'/'spatial_session.json')
