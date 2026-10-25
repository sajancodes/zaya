import math
import uuid
from .component_library import component
from .schema import SpatialScene, Relationship

GENERATORS=('inline_engine','v_engine','electric_motor','gearbox','turbine','motherboard','laptop','battery_pack','robot_arm')


def generate(generator,parameters=None):
    if generator not in GENERATORS:
        raise ValueError('Unknown procedural generator.')
    params=parameters or {}
    if not isinstance(params,dict) or set(params)-{'cylinders','bank_angle','count'}:
        raise ValueError('Unsupported generator parameter.')
    count=params.get('cylinders',4) if generator in ('inline_engine','v_engine') else params.get('count',6)
    if type(count) is not int or not 1<=count<=16:
        raise ValueError('Component count must be 1–16.')
    angle=params.get('bank_angle',90)
    if not isinstance(angle,(int,float)) or not math.isfinite(angle) or not 10<=angle<=150:
        raise ValueError('Bank angle must be 10–150 degrees.')
    if generator=='v_engine' and count%2:
        raise ValueError('A V engine needs an even cylinder count.')
    parts=[];relations=[]
    def add(pid,kind,pos=(0,0,0),**geometry):
        part=component(pid,kind,pos,**geometry);parts.append(part)
        return part
    if generator in ('inline_engine','v_engine'):
        banks=2 if generator=='v_engine' else 1
        crank=add('crankshaft','shaft',(0,0,0),radius=.12,height=count/banks+1)
        crank.transform.rotation=(math.pi/2,0,0)
        for i in range(count):
            bank=i%banks;column=i//banks
            a=math.radians(angle/2)*(1 if bank else -1) if banks==2 else 0
            x,y,z=math.sin(a)*1.1,math.cos(a)*1.1,column-(count/banks-1)/2
            piston=add(f'piston_{i+1}','piston',(x,y,z),radius=.32,height=.4)
            piston.transform.rotation=(0,0,-a)
            rod=add(f'connecting_rod_{i+1}','connecting_rod',(x/2,y/2,z),radius=.065,height=1)
            rod.transform.rotation=(0,0,-a)
            add(f'valve_{i+1}','valve',(x,y+.5,z),radius=.05,height=.4)
            relations.extend((Relationship(source=piston.id,target=rod.id,kind='connected_to'),
                              Relationship(source=rod.id,target='crankshaft',kind='drives')))
        add('casing','housing',(0,.6,0),width=2.5 if banks==2 else 1,height=1.5,depth=count/banks+.7)
    elif generator in ('electric_motor','turbine'):
        add('shaft','shaft',height=3,radius=.14)
        for i in range(count):
            a=i*math.tau/count
            item=add(f'blade_{i+1}','plate',(math.cos(a),0,math.sin(a)),width=.65,height=.15,depth=.5)
            item.transform.rotation=(0,-a,.2)
            relations.append(Relationship(source=item.id,target='shaft',kind='rotates_with'))
        add('casing','housing',width=2.8,height=.8,depth=2.8)
    elif generator=='gearbox':
        for i in range(count):
            add(f'gear_{i+1}','gear',(i*.8-(count-1)*.4,0,0),radius=.5,height=.2,segments=16)
            if i:
                relations.append(Relationship(source=f'gear_{i}',target=f'gear_{i+1}',kind='meshes_with'))
        add('casing','housing',width=count*.8+.5,height=.8,depth=1.4)
    elif generator in ('motherboard','laptop'):
        add('board','pcb',width=4,height=.1,depth=3)
        for i in range(count):
            add(f'chip_{i+1}','chip',((i%4)-1.5,.2,(i//4)-.6),width=.6,height=.2,depth=.5)
        if generator=='laptop':
            screen=add('display','plate',(0,1.5,-1.5),width=4,height=2.5,depth=.1)
            screen.material.color='#3c536e'
    elif generator=='battery_pack':
        for i in range(count):
            add(f'cell_{i+1}','battery',((i%4)*.65,0,(i//4)*.65),width=.5,height=1.2,depth=.5)
            if i:
                relations.append(Relationship(source=f'cell_{i}',target=f'cell_{i+1}',kind='connected_to'))
    else:
        for i in range(min(count,6)):
            add(f'link_{i+1}','connecting_rod',(i*.5,i*.6,0),radius=.12,height=.9)
            add(f'joint_{i+1}','bearing',(i*.5,i*.6-.4,0),radius=.2)
            relations.append(Relationship(source=f'link_{i+1}',target=f'joint_{i+1}',kind='hinged_at'))
    return SpatialScene(scene_id=uuid.uuid4().hex,name=generator.replace('_',' ').title(),parts=parts,
                        relationships=relations,accuracy='SCHEMATIC')
