import json

VERSION=1
MAX_BYTES=512_000


def envelope(kind,session_id,sequence,payload):
    return {'version':VERSION,'type':kind,'session_id':session_id,'sequence':sequence,'payload':payload}


class ClientProtocol:
    """Only renderer telemetry/selection enters Python; never arbitrary commands."""
    def __init__(self,session_id):
        self.session_id,self.sequence=session_id,0

    def accept(self,raw):
        if not isinstance(raw,str) or len(raw.encode())>MAX_BYTES:
            raise ValueError('Message exceeds protocol limits.')
        message=json.loads(raw)
        if not isinstance(message,dict) or set(message)!={'version','type','session_id','sequence','payload'}:
            raise ValueError('Malformed protocol envelope.')
        if message['version']!=VERSION or message['session_id']!=self.session_id:
            raise ValueError('Protocol version or session mismatch.')
        seq=message['sequence']
        if type(seq) is not int or seq<=self.sequence:
            raise ValueError('Duplicate or stale sequence.')
        if message['type'] not in {'renderer.ready','renderer.metrics','selection.changed','view.changed'} or not isinstance(message['payload'],dict):
            raise ValueError('Renderer message type is not allowed.')
        self.sequence=seq
        return message
