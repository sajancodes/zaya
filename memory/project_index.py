"""Local-only project aliases, kept separate from personal prompt memory."""
import json
from pathlib import Path
import time

INDEX_PATH = Path(__file__).resolve().parent / 'projects.json'


def register_project(path: str, name: str, aliases: list[str] | None = None, **metadata) -> dict:
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_dir():
        raise ValueError('Project directory does not exist.')
    records = json.loads(INDEX_PATH.read_text(encoding='utf-8')) if INDEX_PATH.exists() else {}
    records[str(resolved)] = {'name': name, 'path': str(resolved), 'aliases': aliases or [], 'last_seen': time.time(), **metadata}
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = INDEX_PATH.with_suffix('.tmp')
    temporary.write_text(json.dumps(records, indent=2), encoding='utf-8')
    temporary.replace(INDEX_PATH)
    return records[str(resolved)]


def resolve_project(name: str) -> Path:
    records = json.loads(INDEX_PATH.read_text(encoding='utf-8')) if INDEX_PATH.exists() else {}
    matches = [Path(v['path']) for v in records.values() if name.casefold() in {v['name'].casefold(), *(a.casefold() for a in v.get('aliases', []))}]
    if len(matches) == 1:
        return matches[0]
    # Discover exact folder names only; never guess between ambiguous repositories.
    matches = [base / name for base in (Path.home() / 'Desktop', Path.home() / 'Documents', Path.cwd().parent) if (base / name).is_dir()]
    matches = list(dict.fromkeys(p.resolve() for p in matches))
    if len(matches) != 1:
        raise ValueError('Project not found or ambiguous; supply its exact path.')
    return matches[0]
