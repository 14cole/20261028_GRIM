"""Run current-code certification trials after the combined regressions pass."""
import json
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
deadline=time.monotonic()+1200
while not (HERE/'validation_exit_code.txt').exists():
    if time.monotonic()>deadline:raise RuntimeError('Combined validation did not finish')
    time.sleep(1)
if (HERE/'validation_exit_code.txt').read_text().strip()!='0':
    raise RuntimeError('Fix failing regressions before final trials')
for name,case,cap in [('final_inlet_tight','inlet15',3.1),('final_dielectric','dielectric15',8.)]:
    subprocess.run([sys.executable,str(HERE/'study.py'),'--name',name,'--backend',str(ROOT),
        '--case',case,'--cap',str(cap)],check=True)
def pagefiles():
    command='Get-CimInstance Win32_ComputerSystem | Select-Object AutomaticManagedPagefile,TotalPhysicalMemory | ConvertTo-Json -Compress; Get-CimInstance Win32_PageFileUsage | Select-Object Name,AllocatedBaseSize,CurrentUsage,PeakUsage | ConvertTo-Json -Compress'
    output=subprocess.check_output(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],
        text=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    return [json.loads(line) for line in output.splitlines() if line.strip()]
before=pagefiles()
(HERE/'pagefile_before_pressure.json').write_text(json.dumps(before,indent=2)+'\n')
subprocess.run([sys.executable,str(HERE/'pressure_study.py')],check=True)
(HERE/'pagefile_after_pressure.json').write_text(json.dumps(pagefiles(),indent=2)+'\n')
