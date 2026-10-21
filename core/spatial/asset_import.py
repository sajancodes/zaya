"""Bounded local glTF import. No URLs, scripts, arbitrary file serving or model code."""
import hashlib
import json
import mimetypes
import struct
import threading
import uuid
import sqlite3
import re
from contextlib import closing
from pathlib import Path
from urllib.parse import urlparse,unquote
from .schema import SpatialScene,SpatialPart

MAX_IMPORT=32_000_000
_lock=threading.Lock()
_bundles={}
ASSET_DB=Path(__file__).resolve().parents[2]/'memory'/'spatial_assets.db'


def database():
    ASSET_DB.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(ASSET_DB,timeout=10)
    db.execute('CREATE TABLE IF NOT EXISTS assets(bundle_id TEXT,name TEXT,data BLOB,mime TEXT,PRIMARY KEY(bundle_id,name))')
    return db


def resource(bundle_id,name):
    with _lock:
        value=_bundles.get(bundle_id,{}).get(name)
        if value is not None:return value
        if not re.fullmatch(r'[a-f0-9]{32}',bundle_id) or not re.fullmatch(r'(model\.(gltf|glb)|[a-f0-9]{32}\.(bin|png|jpg|jpeg|webp))',name) or not ASSET_DB.is_file():
            return None
        with closing(database()) as db:
            row=db.execute('SELECT data,mime FROM assets WHERE bundle_id=? AND name=?',(bundle_id,name)).fetchone()
            return (bytes(row[0]),row[1]) if row else None


def transform(node):
    if 'matrix' not in node:
        return {'position':node.get('translation',[0,0,0]),'scale':node.get('scale',[1,1,1]),
                'rotation_quaternion':node.get('rotation',[0,0,0,1])}
    import numpy as np
    matrix=np.asarray(node['matrix'],dtype=float).reshape((4,4),order='F')
    if not np.isfinite(matrix).all() or not np.allclose(matrix[3],[0,0,0,1]):
        raise ValueError('Invalid glTF node matrix.')
    scale=np.linalg.norm(matrix[:3,:3],axis=0)
    if np.any(scale<.001):
        raise ValueError('Degenerate imported transform.')
    if np.linalg.det(matrix[:3,:3])<0:
        scale[0]*=-1
    r=matrix[:3,:3]/scale
    if not np.allclose(r.T@r,np.eye(3),atol=.001):
        raise ValueError('Sheared node transforms are unsupported.')
    trace=np.trace(r)
    if trace>0:
        s=(trace+1)**.5*2;q=[(r[2,1]-r[1,2])/s,(r[0,2]-r[2,0])/s,(r[1,0]-r[0,1])/s,.25*s]
    else:
        i=int(np.argmax(np.diag(r)));j=(i+1)%3;k=(i+2)%3
        s=(1+r[i,i]-r[j,j]-r[k,k])**.5*2
        q=[0.,0.,0.,0.];q[i]=s*.25;q[j]=(r[j,i]+r[i,j])/s;q[k]=(r[k,i]+r[i,k])/s;q[3]=(r[k,j]-r[j,k])/s
    return {'position':matrix[:3,3].tolist(),'scale':scale.tolist(),'rotation_quaternion':q}


def import_asset(filename):
    path=Path(filename).expanduser().resolve()
    if path.suffix.lower() not in ('.glb','.gltf') or not path.is_file() or path.stat().st_size>MAX_IMPORT:
        raise ValueError('Choose a local GLB/glTF file up to 32 MB.')
    raw=path.read_bytes();binary_chunks=[]
    if path.suffix.lower()=='.glb':
        if len(raw)<20 or struct.unpack_from('<4sII',raw)!=(b'glTF',2,len(raw)):
            raise ValueError('Invalid GLB header.')
        offset=12;json_chunk=None
        while offset<len(raw):
            if offset+8>len(raw):raise ValueError('Truncated GLB chunk.')
            size,kind=struct.unpack_from('<II',raw,offset);offset+=8
            if size%4 or offset+size>len(raw):raise ValueError('Invalid GLB chunk length.')
            value=raw[offset:offset+size];offset+=size
            if kind==0x4E4F534A:
                if json_chunk is not None:raise ValueError('Duplicate GLB JSON chunk.')
                json_chunk=value
            elif kind==0x004E4942:binary_chunks.append(value)
            else:raise ValueError('Unsupported GLB chunk.')
        document=json.loads(json_chunk or b'{}')
    else:
        document=json.loads(raw)
    if not isinstance(document,dict) or document.get('asset',{}).get('version')!='2.0':
        raise ValueError('Only glTF 2.0 assets are supported.')
    nodes=document.get('nodes',[])
    if not isinstance(nodes,list) or not 1<=len(nodes)<=250:
        raise ValueError('Assets must have 1–250 semantic nodes.')
    if len(document.get('meshes',[]))>250 or len(document.get('images',[]))>64:
        raise ValueError('Imported asset exceeds mesh/image limits.')
    vertices=sum(a.get('count',0) for a in document.get('accessors',[]) if a.get('type')=='VEC3')
    if type(vertices) is not int or vertices>2_000_000:
        raise ValueError('Imported vertex/accessor budget exceeded.')
    if len(document.get('accessors',[]))>2000 or len(document.get('animations',[]))>50:
        raise ValueError('Imported accessor/animation budget exceeded.')
    bundle_id=uuid.uuid4().hex;resources={};total=len(raw);pixel_total=0
    for section in ('buffers','images'):
        for entry in document.get(section,[]):
            uri=entry.get('uri')
            if uri is None:
                continue
            parsed=urlparse(uri)
            if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
                raise ValueError('Embedded data URLs and remote asset dependencies are not accepted.')
            dependency=(path.parent/unquote(parsed.path)).resolve()
            if path.parent not in dependency.parents or dependency.suffix.lower() not in ('.bin','.png','.jpg','.jpeg','.webp'):
                raise ValueError('Asset dependencies must stay in the selected model folder.')
            if not dependency.is_file() or dependency.stat().st_size>MAX_IMPORT-total:
                raise ValueError('Imported dependency exceeds the file budget.')
            content=dependency.read_bytes();total+=len(content)
            if section=='images':
                from io import BytesIO
                from PIL import Image
                with Image.open(BytesIO(content)) as image:
                    pixel_total+=image.width*image.height
                    if max(image.size)>8192 or pixel_total>16_000_000:
                        raise ValueError('Imported texture pixel budget exceeded.')
            name=uuid.uuid4().hex+dependency.suffix.lower()
            resources[name]=(content,mimetypes.guess_type(dependency.name)[0] or 'application/octet-stream')
            entry['uri']=name
    def validate_uris(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if key=='uri' and item not in resources:
                    raise ValueError('Unsupported asset extension URI; only validated local resources are allowed.')
                validate_uris(item)
        elif isinstance(value,list):
            for item in value:validate_uris(item)
    validate_uris(document)
    parents={};parts=[];prefix=hashlib.sha256(raw).hexdigest()[:10]
    for i,node in enumerate(nodes):
        if not isinstance(node,dict):raise ValueError('Invalid glTF node.')
        for child in node.get('children',[]):
            if type(child) is not int or not 0<=child<len(nodes) or child in parents:
                raise ValueError('Invalid node child or multiple parents.')
            parents[child]=i
    for i,node in enumerate(nodes):
        pid=f'asset_{prefix}_{i}'
        node['extras']={**(node.get('extras') if isinstance(node.get('extras'),dict) else {}),'zaya_part_id':pid}
        name=str(node.get('name') or f'Unknown node {i}')[:120]
        parts.append(SpatialPart(id=pid,name=name,kind='imported_node',
            parent_id=f'asset_{prefix}_{parents[i]}' if i in parents else None,
            transform=transform(node),geometry={'primitive':'asset','asset_id':bundle_id,'node_index':i}))
    scene=SpatialScene(scene_id=uuid.uuid4().hex,name=path.stem[:160],accuracy='ASSET_BASED',parts=parts)
    encoded=json.dumps(document,allow_nan=False,separators=(',',':')).encode()
    if path.suffix.lower()=='.glb':
        encoded+=b' '*((-len(encoded))%4)
        chunks=struct.pack('<II',len(encoded),0x4E4F534A)+encoded
        for binary in binary_chunks:chunks+=struct.pack('<II',len(binary),0x004E4942)+binary
        encoded=struct.pack('<4sII',b'glTF',2,12+len(chunks))+chunks
    root_name='model'+path.suffix.lower();resources[root_name]=(encoded,'model/gltf-binary' if root_name.endswith('.glb') else 'model/gltf+json')
    with _lock:
        with closing(database()) as db,db:
            used,count=db.execute('SELECT COALESCE(SUM(length(data)),0),COUNT(DISTINCT bundle_id) FROM assets').fetchone()
            if count>=4 or used+sum(len(v[0]) for v in resources.values())>128_000_000:
                raise ValueError('Imported cache is full. Clear old spatial history and unused cache before importing more.')
            db.executemany('INSERT INTO assets(bundle_id,name,data,mime) VALUES(?,?,?,?)',
                           [(bundle_id,name,value[0],value[1]) for name,value in resources.items()])
        _bundles[bundle_id]=resources
    return scene,root_name


def prune(keep):
    if not ASSET_DB.is_file():return 0
    with _lock,closing(database()) as db,db:
        ids={row[0] for row in db.execute('SELECT DISTINCT bundle_id FROM assets')}
        removed=ids-set(keep)
        for bundle in removed:
            db.execute('DELETE FROM assets WHERE bundle_id=?',(bundle,));_bundles.pop(bundle,None)
        return len(removed)
