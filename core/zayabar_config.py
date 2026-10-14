"""Local media paths and bounded desktop companion settings."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / 'zayabar.json'
EMOTIONS = ('neutral', 'happy', 'sad', 'angry', 'surprised')
DEFAULT_TONES = {
    'neutral': 'Warm, relaxed and conversational. Clear natural pacing, not a formal robotic announcer.',
    'happy': 'Cheerful and smiling, with bright melodic intonation and a little more energy. Keep it natural.',
    'sad': 'Soft, caring and empathetic. Gentle lower energy and slightly slower pacing, without melodrama.',
    'angry': 'Playfully annoyed or calmly firm. Shorter phrases and emphatic intonation; never shout or insult.',
    'surprised': 'Briefly lift the pitch and energy in genuine-sounding surprise, then settle into clear speech.'
}


def load_config(path=CONFIG_PATH):
    data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict):
        raise ValueError('zayabar.json must contain a JSON object.')
    for key in ('enabled', 'show_main_window_on_start', 'fit_legs_to_taskbar'):
        if key in data and not isinstance(data[key], bool):
            raise ValueError(f'{key} must be true or false.')
    for key, minimum, maximum, default in [('width', 64, 600, 240), ('height', 64, 600, 240),
                                           ('seat_fraction', .1, .95, .6), ('horizontal_position', 0, 1, .82),
                                           ('reaction_cooldown_seconds', 2, 120, 10), ('reaction_duration_ms', 500, 10000, 2200)]:
        value = data.get(key, default)
        if not isinstance(value, (int, float)) or not minimum <= value <= maximum:
            raise ValueError(f'Invalid {key}; use {minimum} to {maximum}.')
        data[key] = value
    assets = data.get('assets', {})
    if not isinstance(assets, dict) or not isinstance(assets.get('talking', {}), dict):
        raise ValueError('assets and assets.talking must be JSON objects.')
    paths = [assets.get(k, '') for k in ('standby', 'thinking', 'poked')]
    paths += list(assets.get('talking', {}).values())
    if any(not isinstance(p, str) for p in paths):
        raise ValueError('Every image path must be a string.')
    lines = data.get('reaction_lines', ['Ouch! Be gentle!'])
    if not isinstance(lines, list) or not lines or any(not isinstance(s, str) or not s.strip() or len(s) > 160 for s in lines):
        raise ValueError('reaction_lines must contain short nonempty strings.')
    data['reaction_lines'], data['assets'] = lines, assets
    reactions = data.get('poke_reactions', [])
    if not isinstance(reactions, list) or len(reactions) > 30:
        raise ValueError('poke_reactions must be a list of up to 30 voice/image pairs.')
    for item in reactions:
        if not isinstance(item, dict) or not isinstance(item.get('text'), str) or not item['text'].strip() or len(item['text']) > 160:
            raise ValueError('Each poke reaction needs a short text line.')
        if any(not isinstance(item.get(key, ''), str) for key in ('image', 'audio')):
            raise ValueError('Poke image and audio paths must be strings.')
        if item.get('audio') and Path(item['audio']).suffix.lower() != '.wav':
            raise ValueError('Use a local WAV file for instant poke playback.')
    data['poke_reactions'] = reactions
    tones = data.get('emotion_tones', {})
    if not isinstance(tones, dict) or any(k not in EMOTIONS or not isinstance(v, str) or not v.strip() or len(v) > 500 for k, v in tones.items()):
        raise ValueError('emotion_tones must map known emotions to short voice descriptions.')
    data['emotion_tones'] = {**DEFAULT_TONES, **tones}
    return data


def emotion_tones(path=CONFIG_PATH):
    try:
        return load_config(path)['emotion_tones']
    except (ValueError, OSError):
        return dict(DEFAULT_TONES)


def local_path(value, config_path=CONFIG_PATH):
    if not value:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else Path(config_path).parent / path


def asset_path(config, mode, emotion='neutral', config_path=CONFIG_PATH):
    assets = config['assets']
    value = assets.get('talking', {}).get(emotion, '') if mode == 'talking' else assets.get(mode, '')
    if mode == 'talking':
        value = value or assets.get('talking', {}).get('neutral', '')
    value = value or assets.get('standby', '')
    if not value:
        return None
    return local_path(value, config_path)
