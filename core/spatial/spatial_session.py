import threading
import uuid
import math
import time
from .schema import SpatialScene
from .scene_patcher import apply_patch
from .scene_graph import part_context
from .spatial_protocol import envelope


class SpatialSession:
    def __init__(self):
        self.lock=threading.RLock()
        self.session_id=uuid.uuid4().hex
        self.scene=SpatialScene(scene_id=uuid.uuid4().hex,name='Zaya workspace')
        self.selected_part_ids=[]
        self.undo_stack,self.redo_stack=[],[]
        self.sequence=0
        self.renderer_connected=False
        self.listeners=set()
        self.view={'explode':0.,'xray':'normal','slice':None}
        self.camera_state={'alpha':-math.pi/2,'beta':math.pi/2.7,'radius':10.,'target':[0.,0.,0.]}
        self.renderer_metrics={}

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
            return {'scene':self.scene.model_dump(mode='json'),'selected':list(self.selected_part_ids),'view':dict(self.view),'camera':dict(self.camera_state)}

    def replace(self,scene):
        validated=SpatialScene.model_validate(scene)
        with self.lock:
            # Revisions remain monotonic, including scene changes and undo.
            validated=validated.model_copy(update={'revision':self.scene.revision+1})
            self._remember();self.scene=validated;self.selected_part_ids=[]
            self.publish('scene.create',self.snapshot())

    def _remember(self):
        self.undo_stack.append(self.scene.model_copy(deep=True))
        self.undo_stack=self.undo_stack[-20:];self.redo_stack.clear()

    def patch(self,operations,expected_revision):
        with self.lock:
            candidate=apply_patch(self.scene,operations,expected_revision)
            self._remember();self.scene=candidate
            valid={p.id for p in candidate.parts}
            self.selected_part_ids=[p for p in self.selected_part_ids if p in valid]
            self.publish('scene.patch',self.snapshot())

    def history(self,redo=False):
        with self.lock:
            source,target=(self.redo_stack,self.undo_stack) if redo else (self.undo_stack,self.redo_stack)
            if not source:
                raise ValueError('No history in that direction.')
            target.append(self.scene.model_copy(deep=True))
            self.scene=source.pop().model_copy(update={'revision':self.scene.revision+1})
            self.selected_part_ids=[]
            self.publish('scene.patch',self.snapshot())

    def select(self,ids):
        with self.lock:
            if not isinstance(ids,list) or len(ids)>20 or any(not isinstance(pid,str) for pid in ids):
                raise ValueError('Invalid selection.')
            if not set(ids)<={p.id for p in self.scene.parts}:
                raise ValueError('Selection references an unknown part.')
            self.selected_part_ids=list(dict.fromkeys(ids))

    def context(self):
        with self.lock:
            return part_context(self.scene,self.selected_part_ids)

    def set_view(self,change):
        if not isinstance(change,dict) or set(change)-{'explode','xray','slice'}:
            raise ValueError('Unknown view property.')
        value={**self.view,**change}
        amount=value['explode']
        if type(amount) not in (int,float) or not math.isfinite(amount) or not 0<=amount<=5:
            raise ValueError('Invalid explosion amount.')
        if value['xray'] not in ('normal','outer_transparent','selected_transparent','internal_only','wireframe'):
            raise ValueError('Unknown X-ray mode.')
        plane=value['slice']
        if plane is not None and (not isinstance(plane,dict) or set(plane)!={'axis','offset'} or
             plane['axis'] not in ('x','y','z') or type(plane['offset']) not in (int,float) or
             not math.isfinite(plane['offset']) or abs(plane['offset'])>100):
            raise ValueError('Invalid clipping plane.')
        with self.lock:
            self.view={**self.view,**change};self.publish('scene.patch',self.snapshot())

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


session=SpatialSession()
