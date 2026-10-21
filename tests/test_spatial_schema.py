import pytest
from pydantic import ValidationError
from core.spatial.schema import SpatialScene
from core.spatial.procedural_geometry import generate,GENERATORS


@pytest.mark.parametrize('generator',GENERATORS)
def test_generators_are_bounded_semantic_schematics(generator):
    scene=generate(generator)
    assert 1<=len(scene.parts)<=250 and scene.accuracy=='SCHEMATIC'
    assert len({p.id for p in scene.parts})==len(scene.parts)


@pytest.mark.parametrize('change',[
    lambda s:s['parts'].append(s['parts'][0]),
    lambda s:s['parts'][0].update(parent_id=s['parts'][0]['id']),
    lambda s:s['parts'][0].update(parent_id='missing'),
    lambda s:s['parts'][0]['geometry'].update(radius=float('nan')),
    lambda s:s['parts'][0]['geometry'].update(segments=100000),
    lambda s:s['relationships'].append({'source':'missing','target':'crankshaft','kind':'drives'})])
def test_reject_invalid_scene(change):
    scene=generate('inline_engine').model_dump();change(scene)
    with pytest.raises(ValidationError):SpatialScene.model_validate(scene)
