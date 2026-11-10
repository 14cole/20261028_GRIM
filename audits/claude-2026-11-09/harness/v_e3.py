import sys; sys.path.insert(0,'/home/user/20261028_GRIM/tools/GHOST')
import numpy as np, inspect
from ghost_backend.linalg import dense
print([n for n in dir(dense) if not n.startswith('__')][:40])
print(inspect.signature(dense.DenseFactor.__init__)); print(inspect.signature(dense.DenseFactor.solve))
