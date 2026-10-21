from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class PerceptionState:
    foreground_app: str = ''
    foreground_title: str = ''
    activity: str = 'off'
    visible_text: str = ''
    errors: tuple = ()
    changed_regions: tuple = ()
    cursor_region: tuple = ()
    revision: int = 0
    last_updated: float = 0
    text_updated: float = 0
    tracked_region: tuple = ()

    def public(self):
        return asdict(self)
