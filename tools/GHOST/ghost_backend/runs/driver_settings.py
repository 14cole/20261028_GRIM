"""Explicit, copy-isolated settings for local and scheduler driver adapters."""
from collections.abc import Mapping
from copy import deepcopy


class DriverSettings(Mapping):
    """A pickleable snapshot; callers receive copies of mutable setting values.

    Parameter scripts still pass dictionaries to configure(). Drivers keep one
    snapshot per process and pass ordinary dictionaries to spawned workers.
    """

    def __init__(self, values=()):
        self._values = deepcopy(dict(values))

    def __getitem__(self, key):
        return deepcopy(self._values[key])

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name) from None

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def snapshot(self):
        return deepcopy(self._values)

    @classmethod
    def capture(cls, values, required_keys, defaults=()):
        merged = dict(defaults)
        merged.update(values)
        values = merged
        missing = sorted(set(required_keys) - set(values))
        if missing:
            raise ValueError("Driver script is missing parameter(s): " + ", ".join(missing))
        return cls({key: values[key] for key in required_keys})
