from typing import Literal
import math
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid',allow_inf_nan=False)


class Transform(StrictModel):
    position: tuple[float,float,float] = (0,0,0)
    rotation: tuple[float,float,float] = (0,0,0)
    scale: tuple[float,float,float] = (1,1,1)
    rotation_quaternion: tuple[float,float,float,float] | None = None

    @model_validator(mode='after')
    def bounds(self):
        if any(abs(v)>1000 for v in (*self.position,*self.rotation)) or any(not .001<=abs(v)<=100 for v in self.scale):
            raise ValueError('Transform exceeds workspace limits.')
        if self.rotation_quaternion is not None and abs(sum(v*v for v in self.rotation_quaternion)-1)>.01:
            raise ValueError('Quaternion must be normalized.')
        return self


class Geometry(StrictModel):
    primitive: Literal['box','sphere','cylinder','cone','tube','torus','plate','rod','asset'] = 'box'
    asset_id: str | None = Field(default=None,pattern=r'^[a-f0-9]{32}$')
    node_index: int | None = Field(default=None,ge=0,le=249)
    width: float = Field(default=1,gt=0,le=100)
    height: float = Field(default=1,gt=0,le=100)
    depth: float = Field(default=1,gt=0,le=100)
    radius: float = Field(default=.5,gt=0,le=50)
    thickness: float = Field(default=.1,gt=0,le=20)
    segments: int = Field(default=24,ge=3,le=64)

    @model_validator(mode='after')
    def asset(self):
        if self.primitive=='asset' and (self.asset_id is None or self.node_index is None):
            raise ValueError('Imported geometry requires its asset and semantic node index.')
        return self


class Material(StrictModel):
    color: str = Field(default='#dca0ba',pattern=r'^#[0-9a-fA-F]{6}$')
    alpha: float = Field(default=1,ge=0,le=1)
    wireframe: bool = False


class SpatialPart(StrictModel):
    id: str = Field(min_length=1,max_length=80,pattern=r'^[a-zA-Z0-9_-]+$')
    name: str = Field(min_length=1,max_length=120)
    kind: str = Field(default='component',max_length=60)
    parent_id: str | None = None
    transform: Transform = Field(default_factory=Transform)
    geometry: Geometry = Field(default_factory=Geometry)
    material: Material = Field(default_factory=Material)
    layer: Literal['outer','internal','detail'] = 'internal'
    visible: bool = True
    metadata: dict[str,str] = Field(default_factory=dict,max_length=12)

    @field_validator('metadata')
    @classmethod
    def bounded_metadata(cls,value):
        if any(len(k)>80 or len(v)>500 for k,v in value.items()):
            raise ValueError('Part metadata is too large.')
        return value


class Relationship(StrictModel):
    source: str
    target: str
    kind: str = Field(max_length=60)


class SpatialScene(StrictModel):
    schema_version: Literal[1] = 1
    scene_id: str = Field(min_length=1,max_length=80)
    name: str = Field(min_length=1,max_length=160)
    revision: int = Field(default=0,ge=0)
    accuracy: Literal['SCHEMATIC','REFERENCE_APPROXIMATION','ASSET_BASED','ENGINEERING_SOURCE'] = 'SCHEMATIC'
    parts: list[SpatialPart] = Field(default_factory=list,max_length=250)
    relationships: list[Relationship] = Field(default_factory=list,max_length=500)

    @model_validator(mode='after')
    def graph(self):
        ids={p.id for p in self.parts}
        if len(ids)!=len(self.parts):
            raise ValueError('Part IDs must be unique.')
        parents={p.id:p.parent_id for p in self.parts}
        for part in self.parts:
            seen={part.id};node=part.parent_id;depth=0
            while node is not None:
                if node not in ids or node in seen:
                    raise ValueError('Unknown parent or parent cycle.')
                seen.add(node);node=parents[node];depth+=1
                if depth>12:
                    raise ValueError('Maximum graph depth is 12.')
        for relation in self.relationships:
            if relation.source not in ids or relation.target not in ids:
                raise ValueError('Relationship references an unknown part.')
        return self
