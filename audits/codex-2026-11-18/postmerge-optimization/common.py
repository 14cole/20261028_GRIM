"""Self-contained physical fixtures; lengths are metres and k is radians/metre."""
import numpy as np
from types import SimpleNamespace
from ghost_backend.twod.geometry import LinearNode,LinearElement,LinearMesh

def mesh_for(n,shape):
 if shape in ('star','circle'):
  theta=np.linspace(0,2*np.pi,n,endpoint=False)
  radius=1+.2*np.cos(5*theta) if shape=='star' else np.ones(n)
  xy=np.column_stack((radius*np.cos(theta),radius*np.sin(theta)))
 else:
  vertices={'square':[[-1,-1],[1,-1],[1,1],[-1,1]],'slot':[[-1,-1],[1,-1],[1,1],[.01,1],[.01,-.5],[-.01,-.5],[-.01,1],[-1,1]]}[shape]
  v=np.asarray(vertices,float);assert n%len(v)==0
  xy=np.concatenate([a+(b-a)*np.arange(n//len(v))[:,None]/(n//len(v)) for a,b in zip(v,np.roll(v,-1,axis=0))])
 nodes=[LinearNode(p,(i,0)) for i,p in enumerate(xy)];elements=[]
 for i,p in enumerate(xy):
  j=(i+1)%n;d=xy[j]-p;length=float(np.linalg.norm(d));t=d/length
  elements.append(LinearElement('body',2,0,0,0,(i,j),p,xy[j],(p+xy[j])/2,t,np.array([-t[1],t[0]]),length,i))
 return LinearMesh(nodes,elements)

def exact_rows(oracle,rows,n):
 result=np.empty((len(rows),n),complex)
 for start in range(0,len(rows),16):
  for col in range(0,n,8192):
   result[start:start+16,col:col+8192]=oracle.get(rows[start:start+16],np.arange(col,min(col+8192,n)))
 return result
