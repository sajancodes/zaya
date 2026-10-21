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


def test_large_engine_patch_preserves_compatible_ids_without_clearing_scene():
    session=SpatialSession();old=generate('inline_engine',{'cylinders':4});session.replace(old.model_dump())
    target=generate('v_engine',{'cylinders':8});existing={part.id for part in session.scene.parts}
    old_parts={part.id:part for part in session.scene.parts}
    operations=[{'op':'scene.update','path':'name','value':'V8 engine'}]
    for part in target.parts:
        if part.id not in existing:operations.append({'op':'add','value':part.model_dump()})
        else:
            operations.extend([{'op':'update','part_id':part.id,'path':'transform.position','value':part.transform.position},
                               {'op':'update','part_id':part.id,'path':'transform.rotation','value':part.transform.rotation}])
            for key in ('width','height','depth','radius','thickness','segments'):
                if getattr(part.geometry,key)!=getattr(old_parts[part.id].geometry,key):
                    operations.append({'op':'update','part_id':part.id,'path':'geometry.'+key,'value':getattr(part.geometry,key)})
    for relation in target.relationships:
        operations.append({'op':'relationship.add','value':relation.model_dump()})
    scene_id=session.scene.scene_id
    session.patch(operations,session.scene.revision)
    assert session.scene.scene_id==scene_id and session.scene.name=='V8 engine'
    assert existing<={part.id for part in session.scene.parts}
    assert len([p for p in session.scene.parts if p.kind=='piston'])==8
    assert next(p for p in session.scene.parts if p.id=='casing').geometry.width==2.5
    with pytest.raises(ValueError):session.patch([{'op':'scene.update','path':'accuracy','value':'ENGINEERING_SOURCE'}],session.scene.revision)
