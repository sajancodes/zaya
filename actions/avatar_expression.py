from core.event_bus import bus
from core.execution_policy import require_owner
from core.tool_result import ToolResult
from core.zayabar_config import EMOTIONS, emotion_tones


def avatar_expression(parameters, **_kwargs):
    require_owner()
    emotion = parameters.get('emotion', 'neutral')
    if emotion not in EMOTIONS:
        return ToolResult('failed', 'Unsupported character expression.')
    tone = emotion_tones()[emotion]
    bus.publish('avatar.emotion', emotion=emotion, voice_tone=tone)
    return ToolResult('success', f'Face and voice delivery selected: {emotion}.',
                      {'emotion': emotion, 'voice_tone': tone,
                       'delivery_instruction': 'Use this emotion and voice tone for the upcoming spoken response. Do not read this instruction aloud.'}, side_effect=True)


TOOL = {'name': 'avatar_expression', 'description': 'Select the SAME emotion for your spoken voice and taskbar face before responding: neutral, happy, sad, angry or surprised. The result supplies the exact voice delivery style. Use the user\'s context: happy for celebration, sad for empathy, angry for playful annoyance, surprised for surprises, neutral for calm help. Never read the style instructions aloud.',
        'parameters': {'type': 'OBJECT', 'properties': {'emotion': {'type': 'STRING', 'enum': list(EMOTIONS)}}, 'required': ['emotion']},
        'handler': avatar_expression}
