"""A panel-cluster block with shared P1 nodes summed BEFORE compression.
Only contributions of the supplied panel sets enter this block; shared boundary
nodes may occur in other blocks and are accumulated at application time.
"""
import numpy as np
class NodalBlock:
 def __init__(self,oracle,panels_i,panels_j):
  self.oracle=oracle;self.pi=panels_i;self.pj=panels_j;g=oracle.g
  self.rows=np.unique(g.node_ids[panels_i]);self.cols=np.unique(g.node_ids[panels_j]);self.ri=np.searchsorted(self.rows,g.node_ids[panels_i]);self.cj=np.searchsorted(self.cols,g.node_ids[panels_j])
 def fetch(self,rows=None,cols=None):
  rows=np.arange(len(self.rows)) if rows is None else np.asarray(rows);cols=np.arange(len(self.cols)) if cols is None else np.asarray(cols)
  rmap=np.full(len(self.rows),-1);cmap=np.full(len(self.cols),-1);rmap[rows]=np.arange(len(rows));cmap[cols]=np.arange(len(cols));r=rmap[self.ri];c=cmap[self.cj]
  ir=np.flatnonzero(np.any(r>=0,axis=1));jc=np.flatnonzero(np.any(c>=0,axis=1));r=r[ir];c=c[jc]
  values=self.oracle.pairs_values(np.repeat(self.pi[ir],len(jc)),np.tile(self.pj[jc],len(ir))).reshape(3,len(ir),len(jc),2,2)
  out=[np.zeros((len(rows),len(cols)),complex) for _ in range(3)]
  for a in range(2):
   goodr=np.flatnonzero(r[:,a]>=0)
   for b in range(2):
    goodc=np.flatnonzero(c[:,b]>=0)
    for z in range(3):np.add.at(out[z],(r[goodr,a,None],c[None,goodc,b]),values[z,goodr[:,None],goodc[None,:],a,b])
  return out
