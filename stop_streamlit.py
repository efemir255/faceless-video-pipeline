import subprocess
import shlex
import sys

print('Searching for process listening on port 8501...')
try:
    res = subprocess.run('netstat -aon', capture_output=True, text=True, shell=True)
    out = res.stdout.splitlines()
    pids = set()
    for line in out:
        if ':8501' in line:
            parts = [p for p in line.split() if p]
            if parts:
                pid = parts[-1]
                if pid.isdigit():
                    pids.add(pid)
    if not pids:
        print('No process found listening on port 8501')
        sys.exit(0)
    for pid in pids:
        print(f'Killing PID {pid}...')
        k = subprocess.run(['taskkill', '/PID', pid, '/F'], capture_output=True, text=True)
        print(k.stdout)
        if k.returncode != 0:
            print('Failed to kill', pid, k.stderr)
    print('Done')
except Exception as e:
    print('Error:', e)
    sys.exit(1)
