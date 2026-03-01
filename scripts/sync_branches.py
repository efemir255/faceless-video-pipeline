import subprocess
import sys
import shlex

def run(cmd):
    print('> '+cmd)
    p = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    print(p.stdout, end='')
    if p.stderr:
        print(p.stderr, end='', file=sys.stderr)
    return p.returncode, p.stdout.strip()

# Ensure we fetched
run('git fetch --all --prune')

# Get remote branches under origin
code, out = run("git for-each-ref --format='%(refname:short)' refs/remotes/origin")
if code != 0:
    sys.exit(1)

branches = []
for line in out.splitlines():
    line = line.strip().strip("'\"")
    if not line:
        continue
    # line like origin/branch
    if line.startswith('origin/') and line != 'origin/HEAD':
        branches.append(line[len('origin/'):])

print('\nFound remote branches:')
for b in branches:
    print(' -', b)

for b in branches:
    print('\n=== Processing', b)
    # check if local exists
    code_local, _ = run(f'git show-ref --verify --quiet refs/heads/{shlex.quote(b)}')
    if code_local == 0:
        print('Local branch exists')
        # compare
        code_cmp, out_cmp = run(f'git rev-list --left-right --count {shlex.quote(b)}...origin/{shlex.quote(b)}')
        if code_cmp != 0:
            print('Could not compare branches; skipping')
            continue
        parts = out_cmp.split()
        if len(parts) != 2:
            print('Unexpected rev-list output:', out_cmp)
            continue
        left, right = int(parts[0]), int(parts[1])
        print(f'Divergence: local {left} commits ahead, remote {right} commits ahead')
        if left == 0 and right > 0:
            print('Fast-forwarding local branch')
            rc, _ = run(f'git checkout {shlex.quote(b)}')
            if rc != 0:
                print('Failed to checkout branch; skipping')
                continue
            rc2, _ = run('git merge --ff-only origin/' + shlex.quote(b))
            if rc2 != 0:
                print('Fast-forward failed; you may need to merge/rebase manually')
            else:
                print('Fast-forwarded')
            # return to previous branch
            run('git checkout -')
        elif right == 0 and left > 0:
            print('Local has commits ahead of origin; skipping to avoid overwriting')
        elif left > 0 and right > 0:
            print('Branches have diverged; skipping')
        else:
            print('Up to date')
    else:
        print('Local branch missing; creating tracking branch')
        rc, _ = run(f'git branch --track {shlex.quote(b)} origin/{shlex.quote(b)}')
        if rc == 0:
            print('Created local tracking branch', b)
        else:
            print('Failed to create tracking branch; maybe branch missing on origin')

print('\nDone')
