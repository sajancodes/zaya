from .schema import SpatialPart

COMPONENTS={
    'bolt':'cylinder','screw':'cylinder','nut':'torus','washer':'torus','shaft':'rod',
    'bearing':'torus','gear':'cylinder','spring':'torus','piston':'cylinder',
    'connecting_rod':'rod','valve':'rod','pipe':'tube','housing':'box','fan':'cylinder',
    'wheel':'cylinder','wire':'rod','pcb':'plate','chip':'box','connector':'box','battery':'box'}


def component(part_id,kind,position=(0,0,0),parent=None,**geometry):
    primitive=COMPONENTS.get(kind,kind)
    return SpatialPart(id=part_id,name=part_id.replace('_',' ').title(),kind=kind,parent_id=parent,
        transform={'position':position},geometry={'primitive':primitive,**geometry},
        layer='outer' if kind=='housing' else 'internal')
