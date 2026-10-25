from core.spatial.spatial_session import SpatialSession
from core.spatial.procedural_geometry import generate
from actions.spatial_workspace import spatial_workspace
from unittest.mock import patch
import pytest


def test_annotations_are_validated_undoable_and_removed_with_parts():
    session=SpatialSession();session.replace(generate('inline_engine').model_dump());session.select(['piston_1'])
    with patch('core.spatial.spatial_session.session',session):
        assert spatial_workspace({'action':'annotate','text':'Piston crown','annotation_id':'label_1'}).status=='success'
    assert session.context()['annotations'][0]['text']=='Piston crown'
    assert session.context()['related_parts'][0]['id']=='connecting_rod_1'
    session.patch([{'op':'remove','part_id':'piston_1'}],session.scene.revision)
    assert not session.scene.annotations
    session.history();assert len(session.scene.annotations)==1


def test_scoped_explosion_reassembles_only_selected_part():
    session=SpatialSession();session.replace(generate('inline_engine').model_dump());session.select(['piston_1'])
    with patch('core.spatial.spatial_session.session',session):
        assert spatial_workspace({'action':'explode','scope':'all','amount':1}).status=='success'
        assert spatial_workspace({'action':'reassemble','scope':'selected'}).status=='success'
    assert session.view['explode']==1 and session.view['explode_parts']=={'piston_1':0}


def test_custom_plane_normalized_and_invalid_view_is_atomic():
    session=SpatialSession();session.set_view({'slice':{'normal':[2,0,0],'offset':1}})
    assert session.view['slice']=={'normal':[1,0,0],'offset':.5}
    before=dict(session.view)
    with pytest.raises(ValueError):session.set_view({'slice':{'normal':[0,0,0],'offset':0}})
    assert session.view==before


def test_view_filters_deleted_semantic_targets():
    session=SpatialSession();session.replace(generate('inline_engine').model_dump())
    session.set_view({'explode_parts':{'piston_1':2}})
    session.patch([{'op':'remove','part_id':'piston_1'}],session.scene.revision)
    assert not session.view['explode_parts']
