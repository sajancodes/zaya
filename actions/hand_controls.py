from core.execution_policy import require_owner
from core.tool_result import ToolResult


def _resolve_hand_model(explicit_path=None) -> str:
    from pathlib import Path
    from core.gesture.hand_tracker import DEFAULT_MODEL
    if explicit_path:
        return str(explicit_path)
    if DEFAULT_MODEL.is_file():
        return str(DEFAULT_MODEL)
    from core.runtime_paths import find_or_download_hand_model
    try:
        return str(find_or_download_hand_model())
    except Exception as exc:
        raise RuntimeError(f"Hand tracking model is missing and auto-download failed: {exc}") from exc


def hand_controls(parameters, **kwargs):
    require_owner()
    from core.gesture.controller import hands
    action = parameters.get('action', 'status')
    mode = parameters.get('mode')
    try:
        from core.gesture.settings import load, save, HandSettings
        from dataclasses import asdict
        settings_error = ''
        try:
            settings = load()
        except (ValueError, TypeError, OSError):
            settings = HandSettings()
            settings_error = 'Saved hand settings are invalid; defaults are shown. Configure or start to replace them.'

        if action in ('start', 'configure'):
            settings = HandSettings(**{**asdict(settings), **{k: parameters[k] for k in asdict(settings) if k in parameters}})
            if action == 'configure' and hands.tracker.state in ('ACTIVE', 'STARTING'):
                return ToolResult('failed', 'Stop or pause hand controls before changing settings.')
            save(settings)

        if action == 'settings':
            from core.ghost_overlay import show_vision_control_center, passive_overlay_available
            if not passive_overlay_available():
                return ToolResult('failed', 'The desktop settings panel is unavailable.')
            show_vision_control_center(mode=mode)

        elif action == 'show':
            if hands.tracker.state != 'ACTIVE':
                start_mode = mode or 'NAVIGATION'
                model_path = _resolve_hand_model(parameters.get('model_path'))
                hands.start(model_path, start_mode,
                            settings.device, settings.fps, settings.mirror, settings.confidence, settings.sensitivity)
            elif mode:
                hands.set_mode(mode, settings.sensitivity)

        elif action == 'start':
            target_mode = str(mode or 'NAVIGATION')
            from core.ghost_overlay import passive_overlay_available
            if target_mode == 'KEYBOARD' and not passive_overlay_available():
                return ToolResult('failed', 'The desktop overlay is unavailable; hand typing was not enabled.')
            model_path = _resolve_hand_model(parameters.get('model_path'))
            hands.start(model_path, target_mode,
                        settings.device, settings.fps, settings.mirror, settings.confidence, settings.sensitivity)
            if target_mode == 'KEYBOARD':
                hands.toggle_keyboard(True)

        elif action == 'set_mode':
            if not mode:
                raise ValueError('Specify a mode to switch to (NAVIGATION, KEYBOARD, SPATIAL, SELECTION).')
            if mode == 'KEYBOARD':
                from core.ghost_overlay import passive_overlay_available
                if not passive_overlay_available():
                    return ToolResult('failed', 'The desktop overlay is unavailable; hand typing was not enabled.')
                hands.toggle_keyboard(True)
            hands.set_mode(mode, settings.sensitivity)

        elif action in ('read_text', 'read_selection', 'read_selected_text'):
            from actions.read_selected_text import read_selected_text
            return read_selected_text(parameters, **kwargs)

        elif action == 'show_keyboard':
            hands.toggle_keyboard(True)
        elif action == 'hide_keyboard':
            hands.toggle_keyboard(False)
        elif action == 'toggle_keyboard':
            hands.toggle_keyboard()

        elif action == 'pause':
            hands.pause()
        elif action == 'resume':
            hands.resume()
        elif action == 'stop':
            if mode == 'KEYBOARD' or parameters.get('target') == 'keyboard':
                hands.set_mode('NAVIGATION')
                hands.toggle_keyboard(False)
            else:
                hands.stop()
        elif action not in ('status', 'configure'):
            raise ValueError('Use start, stop, pause, resume, show, set_mode, settings, read_text, or status.')

        state = hands.status()
        state['settings'] = asdict(settings)
        state['settings_error'] = settings_error
        summary = f"Hand controls: {state['camera']}. {state['error']}".strip()
        return ToolResult('failed' if state['camera'] == 'ERROR' else 'partial' if state['camera'] == 'STARTING' else 'success',
                          summary, data=state, side_effect=action not in ('status',))
    except (ValueError, TypeError, RuntimeError, OSError) as error:
        return ToolResult('failed', str(error))


TOOL = {
    'name': 'hand_controls',
    'description': (
        "Owner-only opt-in webcam and hand gesture intelligence for global Windows interaction. "
        "Natural command routing: "
        "- 'read this text', 'read selected text': action='read_text' (reads text selected with two-finger gesture or OS selection). "
        "- 'show/hide keyboard': action='show_keyboard' / 'hide_keyboard' (toggles top Holographic Air Keyboard HUD). "
        "- 'open/start virtual keyboard', 'type with my hands': action='start', mode='KEYBOARD' (enables global typing HUD). "
        "- 'start/open hand controls', 'open camera': action='start', mode='NAVIGATION' (global desktop mouse/select/scroll). "
        "- 'start spatial controls': action='set_mode', mode='SPATIAL' (enables 3D workspace manipulation). "
        "- 'stop hand controls', 'turn off camera': action='stop'. "
        "Camera and models are local; monitor-first interaction without stealing focus."
    ),
    'parameters': {
        'type': 'OBJECT',
        'properties': {
            'action': {'type': 'STRING', 'enum': ['start', 'stop', 'pause', 'resume', 'configure', 'settings', 'status', 'show', 'set_mode', 'read_text', 'show_keyboard', 'hide_keyboard', 'toggle_keyboard']},
            'mode': {'type': 'STRING', 'enum': ['NAVIGATION', 'KEYBOARD', 'SPATIAL', 'SELECTION']},
            'target': {'type': 'STRING', 'description': "Optional target to stop, e.g. 'keyboard' to only close keyboard and keep webcam on."},
            'model_path': {'type': 'STRING'},
            'device': {'type': 'INTEGER'},
            'fps': {'type': 'INTEGER'},
            'mirror': {'type': 'BOOLEAN'},
            'confidence': {'type': 'NUMBER'},
            'sensitivity': {'type': 'NUMBER'}
        }
    },
    'handler': hand_controls
}
