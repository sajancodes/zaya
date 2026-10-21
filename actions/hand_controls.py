from core.execution_policy import require_owner
from core.tool_result import ToolResult


def hand_controls(parameters, **kwargs):
    require_owner()
    from core.gesture.controller import hands
    action = parameters.get('action','status')
    try:
        if action == 'start':
            # Opening the keyboard is an explicit owner-authorized typing session.
            from core.ghost_overlay import passive_overlay_available
            if not passive_overlay_available():
                return ToolResult('failed','The desktop overlay is unavailable; hand typing was not enabled.')
            from core.gesture.hand_tracker import DEFAULT_MODEL
            hands.start(str(parameters.get('model_path') or DEFAULT_MODEL),str(parameters.get('mode') or 'NAVIGATION'),
                        parameters.get('device',0),parameters.get('fps',24),parameters.get('mirror',True))
        elif action in ('stop','pause'):
            hands.stop()
        elif action != 'status':
            raise ValueError('Use start, stop, pause or status.')
        state = hands.status()
        return ToolResult('failed' if state['camera']=='ERROR' else 'partial' if state['camera']=='STARTING' else 'success',
                          'Hand controls: '+state['camera']+'. '+state['error'],data=state,side_effect=action!='status')
    except (ValueError,RuntimeError,OSError) as error:
        return ToolResult('failed',str(error))


TOOL = {'name':'hand_controls','description':'Owner-only opt-in local hand tracking. KEYBOARD authorizes hand-poke typing; SPATIAL enables local orbit, zoom, point/poke selection and pinch manipulation in the open spatial renderer. SELECTION only points/pokes. Camera/model are optional and local; unavailable features do not affect Zaya.',
        'parameters':{'type':'OBJECT','properties':{
            'action':{'type':'STRING','enum':['start','stop','pause','status']},
            'mode':{'type':'STRING','enum':['NAVIGATION','KEYBOARD','SPATIAL','SELECTION']},'model_path':{'type':'STRING'},
            'device':{'type':'INTEGER'},'fps':{'type':'INTEGER'},'mirror':{'type':'BOOLEAN'}}},'handler':hand_controls}
