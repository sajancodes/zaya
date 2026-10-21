import pytest
from core.spatial.spatial_session import SpatialSession
from core.spatial.procedural_geometry import generate


def test_atomic_patch_undo_redo_and_revision():
    session=SpatialSession();session.replace(generate('inline_engine').model_dump())
    previous=session.scene.model_dump();revision=session.scene.revision
    with pytest.raises(ValueError):
        session.patch([{'op':'update','part_id':'piston_1','path':'geometry.radius','value':.8},
                       {'op':'update','part_id':'missing','path':'name','value':'bad'}],revision)
    assert session.scene.model_dump()==previous
    session.patch([{'op':'update','part_id':'piston_1','path':'geometry.radius','value':.8}],revision)
    changed=session.scene.revision
    session.history();assert session.scene.model_dump()['parts']==previous['parts']
    assert session.scene.revision>changed
    session.history(redo=True);assert session.scene.parts[1].geometry.radius==.8
    with pytest.raises(ValueError):session.patch([{'op':'remove','part_id':'piston_1'}],revision)


def test_remove_cleans_relationships_and_selection():
    session=SpatialSession();session.replace(generate('inline_engine').model_dump());session.select(['piston_1'])
    session.patch([{'op':'remove','part_id':'piston_1'}],session.scene.revision)
    assert not session.selected_part_ids and all(r.source!='piston_1' for r in session.scene.relationships)


def test_failed_renderer_listener_does_not_break_python_state():
    session=SpatialSession()
    def dead(packet):raise RuntimeError('renderer gone')
    session.listeners.add(dead);session.replace(generate('v_engine',{'cylinders':8}).model_dump())
    assert len(session.scene.parts)>20 and dead not in session.listeners
