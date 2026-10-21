import json
import struct
import pytest
from core.spatial import asset_import


@pytest.fixture(autouse=True)
def registry(tmp_path,monkeypatch):
    monkeypatch.setattr(asset_import,'ASSET_DB',tmp_path/'assets.db')
    asset_import._bundles.clear()
    yield
    asset_import._bundles.clear()


def document():
    return {'asset':{'version':'2.0'},'scene':0,'scenes':[{'nodes':[0]}],
            'nodes':[{'name':'Assembly','children':[1],'translation':[1,2,3]},
                     {'name':'Piston_L1','mesh':0,'rotation':[0,0,0,1]}],
            'meshes':[{'primitives':[{'attributes':{'POSITION':0}}]}],
            'buffers':[{'uri':'mesh.bin','byteLength':36}],
            'bufferViews':[{'buffer':0,'byteOffset':0,'byteLength':36}],
            'accessors':[{'bufferView':0,'componentType':5126,'count':3,'type':'VEC3','min':[-1,0,0],'max':[1,1,0]}]}


def test_gltf_hierarchy_names_transforms_and_private_resources(tmp_path):
    data=document();(tmp_path/'mesh.bin').write_bytes(struct.pack('<9f',-1,0,0,1,0,0,0,1,0))
    path=tmp_path/'engine.gltf';path.write_text(json.dumps(data))
    scene,root=asset_import.import_asset(path)
    assert scene.accuracy=='ASSET_BASED' and scene.parts[1].name=='Piston_L1'
    assert scene.parts[1].parent_id==scene.parts[0].id
    assert scene.parts[0].transform.position==(1.,2.,3.)
    bundle=scene.parts[0].geometry.asset_id
    output=json.loads(asset_import.resource(bundle,root)[0])
    assert output['nodes'][1]['extras']['zaya_part_id']==scene.parts[1].id
    assert output['buffers'][0]['uri']!='mesh.bin'
    assert asset_import.resource(bundle,output['buffers'][0]['uri'])[0]


def test_glb_preserves_binary_and_rewrites_semantic_extras(tmp_path):
    data=document();data['buffers'][0].pop('uri');encoded=json.dumps(data).encode();encoded+=b' '*((-len(encoded))%4)
    binary=struct.pack('<9f',-1,0,0,1,0,0,0,1,0)
    chunks=struct.pack('<II',len(encoded),0x4E4F534A)+encoded+struct.pack('<II',len(binary),0x004E4942)+binary
    path=tmp_path/'engine.glb';path.write_bytes(struct.pack('<4sII',b'glTF',2,len(chunks)+12)+chunks)
    scene,root=asset_import.import_asset(path)
    result=asset_import.resource(scene.parts[0].geometry.asset_id,root)[0]
    assert result.endswith(binary) and struct.unpack_from('<I',result,8)[0]==len(result)


@pytest.mark.parametrize('uri',['https://example.com/secret.bin','../secret.bin','file:///C:/secret.bin'])
def test_external_or_parent_dependencies_rejected(tmp_path,uri):
    data=document();data['buffers'][0]['uri']=uri
    path=tmp_path/'bad.gltf';path.write_text(json.dumps(data))
    with pytest.raises(ValueError):asset_import.import_asset(path)
    assert not asset_import._bundles


def test_imported_column_major_matrix_decomposes_without_losing_translation():
    result=asset_import.transform({'matrix':[1,0,0,0,0,1,0,0,0,0,1,0,3,4,5,1]})
    assert result['position']==[3,4,5] and result['rotation_quaternion']==[0,0,0,1]
