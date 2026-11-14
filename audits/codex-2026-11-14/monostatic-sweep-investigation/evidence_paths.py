"""Match numeric output batch suffixes without swallowing named batch controls."""
def batches(folder,label):
    return sorted(p for p in folder.glob(label+'-batch*.npz')
                  if len(p.stem[len(label)+len('-batch'):])>=4
                  and p.stem[len(label)+len('-batch'):].isdigit())
