"""Local media paths and bounded desktop companion settings."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / 'zayabar.json'
EMOTIONS = ('neutral', 'happy', 'sad', 'angry', 'surprised')


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
    return data


def asset_path(config, mode, emotion='neutral', config_path=CONFIG_PATH):
    assets = config['assets']
    value = assets.get('talking', {}).get(emotion, '') if mode == 'talking' else assets.get(mode, '')
    if mode == 'talking':
        value = value or assets.get('talking', {}).get('neutral', '')
    value = value or assets.get('standby', '')
    if not value:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else Path(config_path).parent / path
