from run_followups import run
run('tile-refined-0.01',dict(body='diel',n=600,radius=.01,mode='compressed',angles=7,threads=1,force_tile=True,tile_extra_refinement=True))
run('compression-only-final',dict(body='diel',n=2000,radius=.01,mode='compressed',angles=19,compression_only=True))
