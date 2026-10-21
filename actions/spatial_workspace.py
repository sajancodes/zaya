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
        if action=='build':
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
                scene=plan(parameters.get('prompt',''))
            session.replace(scene.model_dump())
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
                    view['explode']=amount
                elif action=='xray':
                    mode=parameters.get('view_mode','outer_transparent')
                    if mode not in ('normal','outer_transparent','selected_transparent','internal_only','wireframe'):
                        raise ValueError('Unknown X-ray mode.')
                    view['xray']=mode
                elif action=='slice':
                    axis=parameters.get('axis','x');offset=float(parameters.get('amount',0))
                    if axis not in ('x','y','z') or not math.isfinite(offset) or abs(offset)>100:
                        raise ValueError('Invalid slicing plane.')
                    view['slice']={'axis':axis,'offset':offset}
                else:
                    view={'explode':0.,'xray':'normal','slice':None}
                session.view=view
                session.publish('scene.patch',session.snapshot())
        elif action=='close':
            from services.spatial_server import stop
            stop()
        elif action not in ('status','context','open'):
            raise ValueError('Unsupported spatial action.')
        data={'revision':session.scene.revision,'parts':len(session.scene.parts),'renderer_connected':session.renderer_connected,
              'selection':session.context(),'view':dict(session.view),'accuracy':session.scene.accuracy}
        return ToolResult('success','Spatial state updated.' if action not in ('status','context') else 'Current semantic spatial context.',
                          data=data,side_effect=action not in ('status','context'))
    except Exception as error:
        return ToolResult('failed',f'Spatial operation failed: {type(error).__name__}: {str(error)[:300]}')


TOOL={'name':'spatial_workspace','description':'Owner-only semantic 3D workspace. Open the local renderer then build a schematic generator or structured AI scene. Modify uses validated patches preserving IDs. Ask context for exact selected part and relationships before answering this/that. Procedural geometry is schematic, never engineering-accurate. No arbitrary scripts or external URLs.',
      'parameters':{'type':'OBJECT','properties':{
          'action':{'type':'STRING','enum':['open','build','patch','modify','select','context','status','undo','redo','explode','reassemble','xray','slice','reset_view','close']},
          'generator':{'type':'STRING','enum':['inline_engine','v_engine','electric_motor','gearbox','turbine','motherboard','laptop','battery_pack','robot_arm']},
          'parameters_json':{'type':'STRING','description':'Generator JSON, e.g. {"cylinders":4}.'},
          'operations_json':{'type':'STRING','description':'Patch operations array; update/add/remove. Use exact IDs and revision.'},
          'prompt':{'type':'STRING'},'revision':{'type':'INTEGER'},'part_id':{'type':'STRING'},
          'amount':{'type':'NUMBER'},'axis':{'type':'STRING'},'view_mode':{'type':'STRING'}}},'handler':spatial_workspace}
