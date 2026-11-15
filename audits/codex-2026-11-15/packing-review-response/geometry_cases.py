"""Deterministic physical 2-D contours. Positive panel counts preserve endpoints."""
import math
import numpy as np
C0=299792458.

def contour(spec, scale=1.):
    length=spec.get('length_m',.1)*scale
    shape=spec.get('shape','circle')
    if shape in ('double_circle','partial'):shape='circle'
    f=spec['frequency_ghz']*1e9
    index=max(1.,abs(complex(*spec.get('eps',[4.,-.2])))**.5) if spec['material']!='pec' else 1.
    spacing=C0/(f*index*spec.get('ppw',20.))
    if shape in ('circle','ellipse','star'):
        pilot=np.linspace(0,2*np.pi,8193)
        def xy(t):
            radius=length/2
            if shape=='star':radius=radius*(1+.22*np.cos(7*t))/1.22
            return np.column_stack((radius*np.cos(t),radius*np.sin(t)*(spec.get('aspect',.25) if shape=='ellipse' else 1.)))
        points=xy(pilot);perimeter=np.linalg.norm(np.diff(points,axis=0),axis=1).sum()
        n=max(48,int(spec['n']*scale) if 'n' in spec else math.ceil(perimeter/spacing))
        points=xy(-np.linspace(0,2*np.pi,n+1));points[-1]=points[0]
        return points
    if shape=='comb':
        teeth=spec.get('teeth',16)
        vertices=[(-1.,-.18),(1.,-.18),(1.,.18)]
        for i in range(1,2*teeth+1):
            x=1.-2*i/(2*teeth+1)
            vertices.extend([(x,vertices[-1][1]),(x,-.16 if vertices[-1][1]>0 else .18)])
        vertices.extend([(-1.,.18),vertices[0]])
        vertices=np.array(vertices)*length/2
    elif shape=='cavity':
        vertices=np.array([[-1,-.3],[1,-.3],[1,-.04],[-.7,-.04],[-.7,.04],[1,.04],[1,.3],[-1,.3],[-1,-.3]])*length/2
    else:raise ValueError(shape)
    points=[]
    for a,b in zip(vertices[:-1],vertices[1:]):
        n=max(1,math.ceil(np.linalg.norm(b-a)/spacing))
        points.extend(a+(b-a)*i/n for i in range(n))
    points.append(points[0])
    return np.array(points[::-1])

def build(spec):
    material=spec['material'];outer=contour(spec);parts=[];sizes=[]
    def add(name,kind,points,r1=0,r2=0):
        sizes.append(len(points)-1)
        lines=['Segment: '+name+' '+str(kind),f'properties: {kind} 1 0 {r1} {r2}']
        lines.extend('%.17g %.17g %.17g %.17g'%(*a,*b) for a,b in zip(points[:-1],points[1:]))
        parts.append('\n'.join(lines))
    if spec.get('shape')=='partial':
        radius=spec.get('length_m',.1)/2;inner=.7*radius
        def arc(r,start,stop,n):
            t=np.linspace(start,stop,n+1);p=np.column_stack((r*np.cos(t),r*np.sin(t)))
            p[[0,-1],1]=0.
            return p
        n=len(outer)-1;half=max(12,int(np.ceil(n/2)));core=max(12,int(np.ceil(.7*n/2)))
        cap=max(2,int(np.ceil(.3*n/(2*np.pi))))
        right=np.column_stack((np.linspace(inner,radius,cap+1),np.zeros(cap+1)))
        left=np.column_stack((np.linspace(-radius,-inner,cap+1),np.zeros(cap+1)))
        outline=np.vstack((right[:-1],arc(radius,0,-np.pi,half)[:-1],left))
        add('bare',2,arc(inner,np.pi,0,core))
        add('core',4,arc(inner,0,-np.pi,core),1)
        add('outline',3,outline,1)
    elif spec.get('shape')=='double_circle':
        shift=spec.get('length_m',.1)/2+spec.get('gap_m',.001)/2
        for i,sign in enumerate((-1,1)):
            points=outer.copy();points[:,0]+=sign*shift
            add('body'+str(i),2 if material=='pec' else 3,points,0 if material=='pec' else 1)
    elif material=='pec':add('body',2,outer)
    else:
        add('outer',3,outer,1)
        if material=='coated':add('core',4,contour(spec,spec.get('inner_ratio',.7)),1)
        if material=='multilayer':
            add('middle',5,contour(spec,.85),1,2)
            add('core',4,contour(spec,.65),2)
    eps=spec.get('eps',[4.,-.2])
    text='Title: synthetic backend stress case\n'+'\n'.join(parts)+'\nIBCS_Resistances:\nDielectrics:\n'
    if material!='pec':text+=f'1 {eps[0]} {eps[1]} 1.0 0.0\n'
    if material=='multilayer':text+='2 9.0 -0.3 1.0 0.0\n'
    return text,dict(input_panels=sum(sizes),boundary_panels=sizes,
        length_m=spec.get('length_m',.1),air_wavelengths=spec.get('length_m',.1)*spec['frequency_ghz']*1e9/C0,
        geometry_sha_basis='generated coordinates and material table')
