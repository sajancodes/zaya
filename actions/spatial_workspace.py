import json
import math
import webbrowser
from core.execution_policy import require_owner
from core.tool_result import ToolResult


def spatial_workspace(parameters, **kwargs):
    require_owner()
    from core.spatial.spatial_session import session
    action=parameters.get('action','status')
    try:
        if action=='open':
            from services.spatial_server import start
            opened=webbrowser.open(start())
            return ToolResult('partial' if not opened else 'success','Local spatial renderer launch requested; connection is confirmed separately.',
                              data={'renderer_connected':session.renderer_connected},side_effect=True)
        if action=='import':
            from core.spatial.asset_import import import_asset
            scene,root_name=import_asset(parameters.get('file_path',''))
            for part in scene.parts:
                part.metadata['asset_file']=root_name
            session.replace(scene.model_dump())
        elif action=='build':
            from core.spatial.procedural_geometry import generate
            from core.spatial.scene_planner import plan
            from core.spatial import spatial_cache
            generator=str(parameters.get('generator') or '')
            raw=parameters.get('parameters_json') or '{}'
            if not isinstance(raw,str) or len(raw)>8000:
                raise ValueError('Generator parameters exceed limits.')
            params=json.loads(raw)
            if generator:
                scene=spatial_cache.load(generator,params) or generate(generator,params)
                spatial_cache.save(generator,params,scene)
            else:
                if not str(parameters.get('prompt') or '').strip():
                    raise ValueError('Describe the scene to build, or choose a generator.')
                from core.spatial.scene_planner import stream_scene
                stream_scene(parameters.get('prompt',''),session)
                scene=None
            if scene is not None:session.replace(scene.model_dump())
        elif action in ('patch','modify'):
            raw=parameters.get('operations_json') or '[]'
            if not isinstance(raw,str) or len(raw)>512_000:
                raise ValueError('Patch exceeds limits.')
            operations=json.loads(raw) if action=='patch' else None
            expected=parameters.get('revision',session.scene.revision)
            if action=='modify':
                from core.spatial.scene_planner import plan
                expected=session.scene.revision
                operations=plan(parameters.get('prompt',''),session)
            session.patch(operations,expected)
        elif action in ('undo','redo'):
            session.history(redo=action=='redo')
        elif action=='annotate':
            import uuid
            target=parameters.get('part_id') or (session.selected_part_ids[0] if session.selected_part_ids else None)
            if target is None:raise ValueError('Select a part to annotate first.')
            session.patch([{'op':'annotation.add','value':{'id':parameters.get('annotation_id') or uuid.uuid4().hex,
                'part_id':target,'text':parameters.get('text','')}}],session.scene.revision)
        elif action=='remove_annotation':
            session.patch([{'op':'annotation.remove','part_id':parameters.get('annotation_id')}],session.scene.revision)
        elif action=='clear':
            from core.spatial.schema import SpatialScene
            import uuid
            session.replace(SpatialScene(scene_id=uuid.uuid4().hex,name='Zaya workspace').model_dump())
        elif action=='clear_history':
            session.clear_history()
        elif action=='clear_cache':
            from core.spatial.asset_import import prune
            prune(session.referenced_assets())
        elif action=='select':
            session.select([parameters['part_id']])
            session.publish('scene.patch',session.snapshot())
        elif action in ('explode','reassemble','xray','slice','reset_view'):
            with session.lock:
                view=dict(session.view)
                if action in ('explode','reassemble'):
                    amount=float(parameters.get('amount',1)) if action=='explode' else 0.
                    if not math.isfinite(amount) or not 0<=amount<=5:
                        raise ValueError('Explosion amount must be 0–5.')
                    scope=parameters.get('scope','all')
                    if scope=='all':view['explode']=amount;view['explode_parts']={}
                    else:
                        ids=set(session.selected_part_ids) if scope=='selected' else {p.id for p in session.scene.parts if p.layer==parameters.get('layer')} if scope=='layer' else {parameters.get('part_id')} if scope=='group' else set()
                        if scope=='group':
                            for _ in range(12):ids|={p.id for p in session.scene.parts if p.parent_id in ids}
                        if not ids or None in ids:raise ValueError('Resolve an explosion target first.')
                        view['explode_parts']={**view.get('explode_parts',{}),**{pid:amount for pid in ids}}
                elif action=='xray':
                    mode=parameters.get('view_mode','outer_transparent')
                    if mode not in ('normal','outer_transparent','selected_transparent','internal_only','wireframe'):
                        raise ValueError('Unknown X-ray mode.')
                    view['xray']=mode
                elif action=='slice':
                    axis=parameters.get('axis','x');offset=float(parameters.get('amount',0))
                    if parameters.get('normal_json'):
                        view['slice']={'normal':json.loads(parameters['normal_json']),'offset':offset}
                    elif axis not in ('x','y','z') or not math.isfinite(offset) or abs(offset)>100:
                        raise ValueError('Invalid slicing plane.')
                    else:view['slice']={'axis':axis,'offset':offset}
                else:
                    view={'explode':0.,'xray':'normal','slice':None}
                session.set_view(view)
        elif action=='close':
            from services.spatial_server import stop
            stop()
        elif action not in ('status','context','open'):
            raise ValueError('Unsupported spatial action.')
        data={'revision':session.scene.revision,'parts':len(session.scene.parts),'renderer_connected':session.renderer_connected,
              'selection':session.context(),'view':dict(session.view),'accuracy':session.scene.accuracy,'renderer_metrics':dict(session.renderer_metrics),'persistence_error':session.persistence_error,'building':session.build_backup is not None}
        return ToolResult('success','Spatial state updated.' if action not in ('status','context') else 'Current semantic spatial context.',
                          data=data,side_effect=action not in ('status','context'))
    except Exception as error:
        return ToolResult('failed',f'Spatial operation failed: {type(error).__name__}: {str(error)[:300]}')


TOOL={'name':'spatial_workspace','description':'Owner-only semantic 3D workspace. Open the local renderer then build a schematic generator or structured AI scene. Modify uses validated patches preserving IDs. Ask context for exact selected part and relationships before answering this/that. Procedural geometry is schematic, never engineering-accurate. No arbitrary scripts or external URLs.',
      'parameters':{'type':'OBJECT','properties':{
          'action':{'type':'STRING','enum':['open','build','import','patch','modify','select','context','status','undo','redo','clear','clear_history','clear_cache','annotate','remove_annotation','explode','reassemble','xray','slice','reset_view','close']},
          'file_path':{'type':'STRING','description':'Owner-selected local .glb or .gltf file. Remote dependencies and path traversal are rejected.'},
          'generator':{'type':'STRING','enum':['inline_engine','v_engine','electric_motor','gearbox','turbine','motherboard','laptop','battery_pack','robot_arm']},
          'parameters_json':{'type':'STRING','description':'Generator JSON, e.g. {"cylinders":4}.'},
          'operations_json':{'type':'STRING','description':'Patch operations array; update/add/remove. Use exact IDs and revision.'},
          'prompt':{'type':'STRING'},'revision':{'type':'INTEGER'},'part_id':{'type':'STRING'},
          'amount':{'type':'NUMBER'},'axis':{'type':'STRING'},'normal_json':{'type':'STRING','description':'Custom plane normal [x,y,z], normalized locally.'},
          'scope':{'type':'STRING','enum':['all','selected','group','layer']},'layer':{'type':'STRING','enum':['outer','internal','detail']},
          'text':{'type':'STRING'},'annotation_id':{'type':'STRING'},'view_mode':{'type':'STRING'}}},'handler':spatial_workspace}
