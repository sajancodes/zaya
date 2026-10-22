"""Private fixed-entry child for optional camera inference; stdout is bounded JSON."""
import json
import os
import sys
import threading
import base64
import re
import time
from .hand_tracker import HandTracker


def _stdin_chunks():
    """Yield stdin bytes without a blocking read holding the GIL.

    A blocking read on a Windows pipe can starve the inference thread while
    MediaPipe/OpenCV are importing. Poll the pipe instead; POSIX uses select.
    """
    if os.name == 'nt':
        import ctypes
        import msvcrt
        from ctypes import wintypes
        handle = wintypes.HANDLE(msvcrt.get_osfhandle(sys.stdin.fileno()))
        available = wintypes.DWORD()
        while True:
            if not ctypes.windll.kernel32.PeekNamedPipe(
                handle, None, 0, None, ctypes.byref(available), None
            ):
                # Manual console run: no pipe metadata.
                data = os.read(sys.stdin.fileno(), 4096)
                if not data:
                    return
                yield data
                continue
            if available.value:
                data = os.read(sys.stdin.fileno(), min(available.value, 4096))
                if not data:
                    return
                yield data
            else:
                time.sleep(0.02)
    else:
        import select
        fd = sys.stdin.fileno()
        while True:
            readable, _, _ = select.select([fd], [], [], 0.1)
            if not readable:
                continue
            data = os.read(fd, 4096)
            if not data:
                return
            yield data


def main():
    os.environ['ZAYA_HAND_CHILD']='1'
    write_lock=threading.Lock()
    def write(packet):
        with write_lock:
            print(json.dumps(packet,allow_nan=False),flush=True)
    def emit(hands):
        def points(values):return [[p.x,p.y,p.z] for p in values]
        packet={'state':tracker.state,'error':tracker.error,'hands':[
            {'id':h.hand_id,'landmarks':points(h.landmarks),'world':points(h.world_landmarks),
             'confidence':h.confidence,'timestamp':h.timestamp} for h in hands]}
        write(packet)
    tracker=HandTracker(emit)
    def control():
        # EOF means the owner process is gone; release camera/model too.
        buffer = ''
        for chunk in _stdin_chunks():
            buffer += chunk.decode('utf-8', 'replace')
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                command = line.strip()
                if command == 'stop':
                    tracker.stop_event.set()
                    return
                if re.fullmatch(r'capture [a-f0-9]{32}', command):
                    frame = tracker.jpeg_snapshot()
                    write({'kind': 'frame', 'id': command.split()[1],
                        'jpeg': base64.b64encode(frame).decode('ascii') if frame else ''})
        tracker.stop_event.set()
    threading.Thread(target=control,daemon=True).start()
    tracker._run(sys.argv[1],int(sys.argv[2]),int(sys.argv[3]),sys.argv[4]=='1',float(sys.argv[5]) if len(sys.argv)>5 else .65)


if __name__=='__main__':
    main()
