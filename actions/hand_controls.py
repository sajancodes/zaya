from core.execution_policy import require_owner
from core.tool_result import ToolResult


def hand_controls(parameters, **kwargs):
    require_owner()
    from core.gesture.controller import hands
    action = parameters.get('action','status')
    try:
        from core.gesture.settings import load,save,HandSettings
        from dataclasses import asdict
        settings_error=''
        try:settings=load()
        except (ValueError,TypeError,OSError):
            settings=HandSettings();settings_error='Saved hand settings are invalid; defaults are shown. Configure or start to replace them.'
        if action in ('start','configure'):
            settings=HandSettings(**{**asdict(settings),**{k:parameters[k] for k in asdict(settings) if k in parameters}})
            if action=='configure' and hands.tracker.state in ('ACTIVE','STARTING'):
                return ToolResult('failed','Stop or pause hand controls before changing settings.')
            save(settings)
        if action=='settings':
            from core.ghost_overlay import show_hand_settings
            if not show_hand_settings():return ToolResult('failed','The desktop settings panel is unavailable.')
            return ToolResult('success','Hand settings panel requested.',side_effect=True)
        if action == 'start':
            # Opening the keyboard is an explicit owner-authorized typing session.
            from core.ghost_overlay import passive_overlay_available
            if not passive_overlay_available():
                return ToolResult('failed','The desktop overlay is unavailable; hand typing was not enabled.')
            from core.gesture.hand_tracker import DEFAULT_MODEL
            hands.start(str(parameters.get('model_path') or DEFAULT_MODEL),str(parameters.get('mode') or 'NAVIGATION'),
                        settings.device,settings.fps,settings.mirror,settings.confidence,settings.sensitivity)
        elif action=='pause':
            hands.pause()
        elif action=='resume':
            hands.resume()
        elif action=='stop':
            hands.stop()
        elif action not in ('status','configure'):
            raise ValueError('Use start, stop, pause or status.')
        state = hands.status()
        state['settings']=asdict(settings)
        state['settings_error']=settings_error
        return ToolResult('failed' if state['camera']=='ERROR' else 'partial' if state['camera']=='STARTING' else 'success',
                          'Hand controls: '+state['camera']+'. '+state['error'],data=state,side_effect=action!='status')
    except (ValueError,TypeError,RuntimeError,OSError) as error:
        return ToolResult('failed',str(error))


TOOL = {'name':'hand_controls','description':'Owner-only opt-in local hand tracking. KEYBOARD authorizes hand-poke typing; SPATIAL enables local orbit, zoom, point/poke selection and pinch manipulation in the open spatial renderer. SELECTION only points/pokes. Camera/model are optional and local; unavailable features do not affect Zaya.',
        'parameters':{'type':'OBJECT','properties':{
            'action':{'type':'STRING','enum':['start','stop','pause','resume','configure','settings','status']},
            'mode':{'type':'STRING','enum':['NAVIGATION','KEYBOARD','SPATIAL','SELECTION']},'model_path':{'type':'STRING'},
            'device':{'type':'INTEGER'},'fps':{'type':'INTEGER'},'mirror':{'type':'BOOLEAN'},
            'confidence':{'type':'NUMBER'},'sensitivity':{'type':'NUMBER'}}},'handler':hand_controls}
