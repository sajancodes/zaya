from copy import deepcopy
from .schema import SpatialScene, SpatialPart, Relationship, Annotation

ALLOWED_PATHS={'name','parent_id','visible','layer','transform.position','transform.rotation','transform.rotation_quaternion','transform.scale',
               'material.color','material.alpha','material.wireframe','geometry.width','geometry.height',
               'geometry.depth','geometry.radius','geometry.thickness','geometry.segments'}


def apply_patch(scene, operations, expected_revision):
    if expected_revision!=scene.revision:
        raise ValueError('Scene revision mismatch; refresh before patching.')
    if not isinstance(operations,list) or not 1<=len(operations)<=100:
        raise ValueError('A patch requires 1–100 operations.')
    candidate=deepcopy(scene.model_dump())
    parts={p['id']:p for p in candidate['parts']}
    for operation in operations:
        if not isinstance(operation,dict) or set(operation)-{'op','part_id','path','value'}:
            raise ValueError('Malformed patch operation.')
        op,pid=operation.get('op'),operation.get('part_id')
        if op=='scene.update':
            if operation.get('path')!='name':raise ValueError('Only the scene name can be patched at scene scope.')
            candidate['name']=operation.get('value')
        elif op in ('annotation.add','annotation.remove'):
            if op=='annotation.add':
                annotation=Annotation.model_validate(operation.get('value')).model_dump()
                if any(a['id']==annotation['id'] for a in candidate['annotations']):raise ValueError('Duplicate annotation ID.')
                candidate['annotations'].append(annotation)
            else:
                if not any(a['id']==pid for a in candidate['annotations']):raise ValueError('Unknown annotation ID.')
                candidate['annotations']=[a for a in candidate['annotations'] if a['id']!=pid]
        elif op in ('relationship.add','relationship.remove'):
            relation=Relationship.model_validate(operation.get('value')).model_dump()
            if op=='relationship.add':
                if relation not in candidate['relationships']:
                    candidate['relationships'].append(relation)
            else:
                if relation not in candidate['relationships']:
                    raise ValueError('Unknown relationship.')
                candidate['relationships'].remove(relation)
        elif op=='add':
            new=SpatialPart.model_validate(operation.get('value')).model_dump()
            if new['id'] in parts:
                raise ValueError('Cannot add a duplicate part ID.')
            parts[new['id']]=new
        elif op=='remove':
            if pid not in parts:
                raise ValueError('Unknown part ID.')
            removed={pid}
            while True:
                children={key for key,p in parts.items() if p['parent_id'] in removed}
                if children<=removed:
                    break
                removed |= children
            parts={key:p for key,p in parts.items() if key not in removed}
            candidate['relationships']=[r for r in candidate['relationships'] if r['source'] not in removed and r['target'] not in removed]
            candidate['annotations']=[a for a in candidate['annotations'] if a['part_id'] not in removed]
        elif op=='update':
            path=operation.get('path')
            if pid not in parts or path not in ALLOWED_PATHS:
                raise ValueError('Unknown part or forbidden patch path.')
            target=parts[pid];keys=path.split('.')
            for key in keys[:-1]:
                target=target[key]
            target[keys[-1]]=operation.get('value')
        else:
            raise ValueError('Unknown patch operation.')
    candidate['parts']=list(parts.values());candidate['revision']+=1
    return SpatialScene.model_validate(candidate)
