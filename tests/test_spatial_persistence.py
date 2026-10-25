from core.spatial.spatial_session import SpatialSession
from core.spatial.procedural_geometry import generate
from core.spatial import asset_import
from test_spatial_assets import document
import json,struct


def test_restore_scene_selection_view_camera_and_undo(tmp_path):
    path=tmp_path/'session.json';session=SpatialSession(path)
    session.replace(generate('inline_engine').model_dump());session.select(['piston_1'])
    session.patch([{'op':'update','part_id':'piston_1','path':'geometry.radius','value':.9}],session.scene.revision)
    session.set_view({'xray':'outer_transparent','slice':{'axis':'x','offset':.5}})
    session.metrics({'fps':60,'camera':{'alpha':1,'beta':1,'radius':8,'target':[1,2,3]}});session.save()
    recovered=SpatialSession(path)
    assert recovered.scene.model_dump()==session.scene.model_dump()
    assert recovered.selected_part_ids==['piston_1'] and recovered.camera_state['radius']==8
    assert recovered.view['xray']=='outer_transparent' and recovered.undo_stack
    assert not recovered.renderer_connected and not recovered.persistence_error
    recovered.history();assert next(p for p in recovered.scene.parts if p.id=='piston_1').geometry.radius==.32


def test_bad_cache_does_not_break_optional_session_and_is_preserved(tmp_path):
    path=tmp_path/'bad.json';path.write_text('[]')
    session=SpatialSession(path)
    assert session.persistence_error and path.read_text()=='[]'


def test_imported_mesh_bytes_survive_memory_reset_and_prune_preserves_references(tmp_path,monkeypatch):
    monkeypatch.setattr(asset_import,'ASSET_DB',tmp_path/'assets.db');asset_import._bundles.clear()
    path=tmp_path/'model.gltf';path.write_text(json.dumps(document()))
    (tmp_path/'mesh.bin').write_bytes(struct.pack('<9f',-1,0,0,1,0,0,0,1,0))
    scene,name=asset_import.import_asset(path);asset=scene.parts[0].geometry.asset_id
    asset_import._bundles.clear()
    assert asset_import.resource(asset,name)[0]
    assert asset_import.prune({asset})==0
    assert asset_import.prune(set())==1
    assert asset_import.resource(asset,name) is None
