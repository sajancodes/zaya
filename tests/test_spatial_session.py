import json
import pytest
pytest.importorskip("fastapi", reason="fastapi not installed")
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from core.spatial.spatial_session import SpatialSession
from core.spatial.spatial_protocol import envelope
from core.spatial.procedural_geometry import generate
from services.spatial_server import make_app


def test_authenticated_reconnect_replays_authoritative_scene_and_selection():
    session=SpatialSession();session.replace(generate('inline_engine').model_dump())
    with TestClient(make_app(session,'secret'),base_url='http://127.0.0.1') as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect('ws://127.0.0.1/ws?token=wrong'):pass
        with client.websocket_connect('ws://127.0.0.1/ws?token=secret') as socket:
            snapshot=socket.receive_json();assert snapshot['payload']['scene']['name']=='Inline Engine'
            socket.send_text(json.dumps(envelope('selection.changed',session.session_id,1,{'ids':['piston_1']})))
        with client.websocket_connect('ws://127.0.0.1/ws?token=secret') as socket:
            assert socket.receive_json()['payload']['selected']==['piston_1']
        assert session.scene.name=='Inline Engine'
