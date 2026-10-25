from .schema import SpatialScene


def part_context(scene: SpatialScene, selected):
    ids=set(selected)
    related={r.target if r.source in ids else r.source for r in scene.relationships if r.source in ids or r.target in ids}-ids
    return {'scene':scene.name,'accuracy':scene.accuracy,'revision':scene.revision,
            'selected':[p.model_dump() for p in scene.parts if p.id in ids],
            'relationships':[r.model_dump() for r in scene.relationships if r.source in ids or r.target in ids],
            'related_parts':[p.model_dump() for p in scene.parts if p.id in related],
            'annotations':[a.model_dump() for a in scene.annotations if a.part_id in ids],
            'children':{p.id:[c.id for c in scene.parts if c.parent_id==p.id] for p in scene.parts if p.id in ids}}
