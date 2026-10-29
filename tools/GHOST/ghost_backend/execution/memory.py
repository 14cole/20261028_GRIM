"""Native current-process memory fallback when optional psutil is absent."""
import os
from functools import lru_cache
from types import SimpleNamespace


def windows_available_commit_bytes():
    """Additional process commit capacity; None means unavailable, zero is real."""
    if os.name != 'nt':
        return None
    try:
        import ctypes
        class Status(ctypes.Structure):
            _fields_ = [('length',ctypes.c_ulong),('load',ctypes.c_ulong)] + [
                (name,ctypes.c_ulonglong) for name in ('total_phys','available_phys',
                'total_commit','available_commit','total_virtual','available_virtual','reserved')]
        status=Status();status.length=ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return int(status.available_commit)
    except (AttributeError,OSError):
        pass
    return None


@lru_cache(maxsize=1)
def _windows_api():
    if os.name != 'nt':
        return None
    try:
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)] + [
                (name,ctypes.c_size_t) for name in ('PeakWorkingSetSize','WorkingSetSize',
                'QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage',
                'QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage','PrivateUsage')]
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        psapi=ctypes.WinDLL('psapi',use_last_error=True)
        kernel.GetCurrentProcess.restype=wintypes.HANDLE
        kernel.GetCurrentProcess.argtypes=[]
        psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
        psapi.GetProcessMemoryInfo.restype=wintypes.BOOL
        return ctypes,Counters,kernel,psapi
    except (AttributeError,OSError):
        return None


def windows_process_memory():
    api=_windows_api()
    if api is None:
        return None
    ctypes,Counters,kernel,psapi=api
    data=Counters();data.cb=ctypes.sizeof(data)
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(data),data.cb):
        return None
    return SimpleNamespace(rss=int(data.WorkingSetSize),private=int(data.PrivateUsage),
                           peak_wset=int(data.PeakWorkingSetSize))
