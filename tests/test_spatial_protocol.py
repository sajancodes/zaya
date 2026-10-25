import json
import pytest
from core.spatial.spatial_protocol import ClientProtocol,envelope


def test_replay_wrong_session_malformed_and_command_rejected():
    protocol=ClientProtocol('session')
    raw=json.dumps(envelope('renderer.ready','session',1,{}));protocol.accept(raw)
    for packet in [raw,json.dumps(envelope('renderer.ready','other',2,{})),
                   json.dumps(envelope('scene.patch','session',2,{})),'[]','bad json']:
        with pytest.raises(ValueError):protocol.accept(packet)
    assert ClientProtocol('session').accept(raw) # Reconnect uses a fresh sequence gate.
