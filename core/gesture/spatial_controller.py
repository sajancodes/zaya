"""Bounded local hand frames to renderer. No provider calls in this path."""
class SpatialController:
    def update(self,hands,events,engine,selection_only=False):
        from core.spatial.spatial_session import session
        import math
        if not session.renderer_connected:
            return
        values=[]
        for hand in hands[:2]:
            active=engine.states.get(hand.hand_id)
            tip=hand.landmarks[8]
            wrist,knuckle=hand.landmarks[0],hand.landmarks[5]
            values.append({'id':hand.hand_id,'pose':active[0] if active and active[2] else 'NONE',
                'x':max(0,min(1,tip.x)),'y':max(0,min(1,tip.y)),
                'palm':[hand.palm_center.x,hand.palm_center.y,hand.palm_center.z],
                'wrist':math.atan2(knuckle.y-wrist.y,knuckle.x-wrist.x)})
        session.publish('interaction.frame',{'hands':values,'selection_only':selection_only,
            'gestures':[event.type for event in events if event.metadata.get('phase')=='enter'],
            'pokes':[event.hand_id for event in events if event.type=='POKE' and event.metadata.get('phase')=='enter']})
