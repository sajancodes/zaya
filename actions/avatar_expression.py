from core.event_bus import bus
from core.execution_policy import require_owner
from core.tool_result import ToolResult
from core.zayabar_config import EMOTIONS


def avatar_expression(parameters, **_kwargs):
    require_owner()
    emotion = parameters.get('emotion', 'neutral')
    if emotion not in EMOTIONS:
        return ToolResult('failed', 'Unsupported character expression.')
    bus.publish('avatar.emotion', emotion=emotion)
    return ToolResult('success', f'Character expression requested: {emotion}.', side_effect=True)


TOOL = {'name': 'avatar_expression', 'description': 'Choose the taskbar character\'s static expression to match your response tone: neutral, happy, sad, angry or surprised. No mouth animation. Use neutral for ordinary assistance; never change computer permissions or behavior through emotion.',
        'parameters': {'type': 'OBJECT', 'properties': {'emotion': {'type': 'STRING', 'enum': list(EMOTIONS)}}, 'required': ['emotion']},
        'handler': avatar_expression}
