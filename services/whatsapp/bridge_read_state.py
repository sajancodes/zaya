"""Add read-state observations to a private copy of the installed Hermes bridge.

The upstream source, credentials and read-receipt policy remain untouched. The
copy stays beside its source so the upstream relative imports still resolve.
"""
from pathlib import Path
import os
import tempfile


ANCHOR = "  sock.ev.on('messages.update', async (updates) => {"
POLL_ANCHOR = 'const msgs = messageQueue.splice(0, messageQueue.length);'
LISTENERS = """
  // Zaya observes account read state; this does not send read receipts.
  const zayaReadState = (chats, history = false) => {
    for (const chat of chats || []) {
      // Baileys emits null for a read action during initial state sync.
      const count = chat.unreadCount === null ? 0 : chat.unreadCount;
      if (typeof chat.id !== 'string' || count !== 0) continue;
      const rawTime = chat.conversationTimestamp;
      const snapshotTime = typeof rawTime?.toNumber === 'function' ? rawTime.toNumber() : Number(rawTime);
      const timestamp = history ? snapshotTime : Date.now() / 1000;
      if (!Number.isFinite(timestamp) || timestamp <= 0) continue;
      const previous = zayaReadStates.get(chat.id);
      if (!previous || timestamp > previous.timestamp) {
        zayaReadStates.set(chat.id, {event: 'chat.read_state', chatId: chat.id,
          unreadCount: 0, timestamp});
      }
      // Read metadata must never evict a real incoming message.
      if (zayaReadStates.size > 4096) zayaReadStates.delete(zayaReadStates.keys().next().value);
    }
  };
  sock.ev.on('chats.update', zayaReadState);
  sock.ev.on('messaging-history.set', ({chats}) => zayaReadState(chats, true));
"""


def instrument(source: str) -> str:
    if source.count(ANCHOR) != 1 or source.count(POLL_ANCHOR) != 1 or 'messageQueue.push(event)' not in source:
        raise ValueError('This Hermes bridge version does not support read-state instrumentation.')
    source = source.replace(ANCHOR, LISTENERS + '\n' + ANCHOR, 1)
    source = source.replace(POLL_ANCHOR, 'const msgs = messageQueue.splice(0, messageQueue.length).concat(Array.from(zayaReadStates.values())); zayaReadStates.clear();', 1)
    declaration = 'const zayaReadStates = new Map();\n'
    if source.startswith('#!'):
        first, source = source.split('\n', 1)
        return first + '\n' + declaration + source
    return declaration + source


def prepare_bridge(bridge: Path) -> Path:
    source = instrument(bridge.read_text(encoding='utf-8'))
    target = bridge.with_name('zaya-read-state-bridge.js')
    if target.exists() and target.read_text(encoding='utf-8') == source:
        return target
    fd, temporary = tempfile.mkstemp(prefix='.zaya-bridge-', suffix='.js', dir=bridge.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(source)
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return target
