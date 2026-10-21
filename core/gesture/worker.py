"""Private fixed-entry child for optional camera inference; stdout is bounded JSON."""
import json
import os
import sys
import threading
import base64
import re
from .hand_tracker import HandTracker


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
        for line in sys.stdin:
            command=line.strip()
            if command=='stop':break
            if re.fullmatch(r'capture [a-f0-9]{32}',command):
                frame=tracker.jpeg_snapshot()
                write({'kind':'frame','id':command.split()[1],
                    'jpeg':base64.b64encode(frame).decode('ascii') if frame else ''})
        tracker.stop_event.set()
    threading.Thread(target=control,daemon=True).start()
    tracker._run(sys.argv[1],int(sys.argv[2]),int(sys.argv[3]),sys.argv[4]=='1',float(sys.argv[5]) if len(sys.argv)>5 else .65)


if __name__=='__main__':
    main()
