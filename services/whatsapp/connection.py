"""Private pointer to the exact Hermes linked-device session; never copy keys."""
import json
from pathlib import Path

CONNECTION_PATH = Path(__file__).resolve().parents[2] / 'config' / 'hermes_connection.json'


def normalize_account(value: str) -> str:
    parts = value.split('@')
    if len(parts) != 2:
        raise ValueError('Invalid linked account identifier.')
    return parts[0].split(':')[0] + '@' + parts[1]


def load_connection(path: Path = CONNECTION_PATH) -> dict | None:
    if not path.exists():
        return None
    record = json.loads(path.read_text(encoding='utf-8'))
    home = Path(record['hermes_home']).expanduser().resolve()
    session = Path(record['session_path']).expanduser().resolve()
    if not session.is_relative_to(home) or not (session / 'creds.json').is_file():
        raise ValueError('The saved Hermes session is missing or outside its profile.')
    # Read identity only; linked-device keys remain in Hermes and never enter
    # the runtime DB, logs, tool results, repository or model context.
    credentials = json.loads((session / 'creds.json').read_text(encoding='utf-8'))
    account = normalize_account(str(credentials.get('me', {}).get('id', '')))
    # Baileys linked-device sessions can retain registered=false after a real
    # successful QR handshake. `me.id` is populated by pairing; actual online
    # readiness is separately verified using the bridge health response.
    if account != normalize_account(record['account_id']):
        raise ValueError('Saved connection does not match the linked account.')
    return {**record, 'hermes_home': str(home), 'session_path': str(session), 'account_id': account}
