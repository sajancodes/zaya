"""Reserve generated artifact names without replacing owner files."""
import os
import re
from pathlib import Path


def sheet_title(value):
    title = re.sub(r'[\[\]:*?/\\]', '_', str(value or '')).strip().strip("'")
    return title[:31] or 'Sheet1'


def save_artifact(writer, requested: Path) -> Path:
    requested = Path(requested)
    requested.parent.mkdir(parents=True, exist_ok=True)
    for number in range(10000):
        path = requested if number == 0 else requested.with_name(f'{requested.stem}_{number}{requested.suffix}')
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            continue
        os.close(descriptor)
        try:
            writer(path)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return path
    raise FileExistsError('No unused output name was available.')
