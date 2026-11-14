"""Compare complete saved fields for matched research sampling policies."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np

def compare_fields(reference,trial):
 reference,trial=Path(reference),Path(trial)
 result=dict(reference=reference.name,trial=trial.name,reference_sha256=hashlib.sha256(reference.read_bytes()).hexdigest(),trial_sha256=hashlib.sha256(trial.read_bytes()).hexdigest())
 with np.load(reference) as a,np.load(trial) as b:
  for key in ['rhs','angles','observation']:assert np.array_equal(a[key],b[key]),key
  for key in ['density','field']:
   x,y=a[key],b[key];assert x.shape==y.shape and np.all(np.isfinite(x)) and np.all(np.isfinite(y)),key
   norm=float(np.linalg.norm(x));peak=float(np.max(abs(x)));assert norm>0 and peak>0,key
   result[key+'_relative_2']=float(np.linalg.norm(y-x)/norm)
   result[key+'_relative_max']=float(np.max(abs(y-x))/peak)
 assert result['field_relative_max']<1e-10,result
 assert result['density_relative_2']<1e-8,result
 return result

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('reference');parser.add_argument('trial');parser.add_argument('--out')
 args=parser.parse_args();result=compare_fields(args.reference,args.trial);text=json.dumps(result,indent=2)
 if args.out:Path(args.out).write_text(text+'\n')
 print(text)
