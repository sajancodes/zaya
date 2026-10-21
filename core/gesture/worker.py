"""Private fixed-entry child for optional camera inference; stdout is bounded JSON."""
import json
import os
import sys
import threading
from .hand_tracker import HandTracker


def main():
    os.environ['ZAYA_HAND_CHILD']='1'
    def emit(hands):
        def points(values):return [[p.x,p.y,p.z] for p in values]
        packet={'state':tracker.state,'error':tracker.error,'hands':[
            {'id':h.hand_id,'landmarks':points(h.landmarks),'world':points(h.world_landmarks),
             'confidence':h.confidence,'timestamp':h.timestamp} for h in hands]}
        print(json.dumps(packet,allow_nan=False),flush=True)
    tracker=HandTracker(emit)
    def control():
        # EOF means the owner process is gone; release camera/model too.
        sys.stdin.readline()
        tracker.stop_event.set()
    threading.Thread(target=control,daemon=True).start()
    tracker._run(sys.argv[1],int(sys.argv[2]),int(sys.argv[3]),sys.argv[4]=='1')


if __name__=='__main__':
    main()
