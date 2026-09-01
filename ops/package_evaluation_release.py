"""Package the dirty evaluation checkout without committing or including secrets."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def digest(data):
    return hashlib.sha256(data.replace(b'\r\n', b'\n')).hexdigest()


def main():
    output = Path(sys.argv[1]).resolve()
    release = sys.argv[2]
    # Pass manifests oldest -> newest when following an older delta release.
    history = [json.loads(Path(p).read_text(encoding='utf-8')) for p in sys.argv[3:]]
    previous = history[-1] if history else None
    previous_files = {}
    for entry in history:
        previous_files.update(entry.get('runtime_snapshot', {}))
        previous_files.update({item['path']: item['sha256'] for item in entry['files']})
    output.mkdir(parents=True, exist_ok=True)
    # VPS runs the merged V4 base, not the evaluation feature's own HEAD.
    changed = subprocess.check_output(['git', 'diff', 'MERGE_HEAD', '--name-only'], cwd=ROOT).decode().splitlines()
    changed += subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard'], cwd=ROOT).decode().splitlines()
    paths = sorted({p for p in changed if (
        p.startswith('agent/') and p.endswith('.py') and '/tests/' not in p
        or p.startswith('backend/') and p.endswith('.js') and '/tests/' not in p
        or p.startswith('analytics_frontend/') and p.endswith(('.js', '.html', '.css')) and '/tests/' not in p
    )})
    manifest = {'release': release, 'branch': subprocess.check_output(['git','branch','--show-current'],cwd=ROOT).decode().strip(),
                'head': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(), 'files': []}
    assert manifest['branch'] == 'codex/v4-live-evaluation'
    if previous:
        assert previous['branch'] == manifest['branch']
        manifest.update(previous_release=previous['release'], preserve_environment=True)
    archive = output / (release + '.tar.gz')
    remote_code = "import pathlib,hashlib,json;root=pathlib.Path('/var/www/agent');print(json.dumps({p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}))"
    remote = json.loads(subprocess.check_output([
        r'C:\Windows\System32\OpenSSH\ssh.exe', '-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
        'root@agent.pawgrammers.io.vn', "python3 -c '" + remote_code.replace("'", "'\"'\"'") + "'"],timeout=60))
    with tarfile.open(archive, 'w:gz') as tar:
        for name in paths:
            source = ROOT / name
            assert source.is_file() and not source.is_symlink()
            data = source.read_bytes()
            if previous and previous_files.get(name) == digest(data):
                continue
            old = []
            for ref in ['HEAD', 'MERGE_HEAD']:
                value = subprocess.run(['git','show',f'{ref}:{name}'],cwd=ROOT,capture_output=True)
                if value.returncode == 0: old.append(digest(value.stdout))
            item = {'path':name, 'sha256':digest(data), 'known_previous':old}
            if previous:
                item['expected_previous'] = previous_files.get(name)
                if item['expected_previous']: item['known_previous'].append(item['expected_previous'])
            manifest['files'].append(item)
            tar.add(source, arcname=name)
        dist = ROOT / 'agent_frontend/dist'
        assert (dist / 'index.html').is_file()
        manifest['frontend_files'] = []
        for source in sorted(dist.rglob('*')):
            if source.is_file():
                assert not source.is_symlink()
                relative = source.relative_to(dist).as_posix()
                sha = hashlib.sha256(source.read_bytes()).hexdigest()
                manifest['frontend_files'].append({'path':relative,'sha256':sha})
                if remote.get(relative) != sha:
                    tar.add(source, arcname='frontend/' + relative)
        manifest['runtime_snapshot'] = {**previous_files, **{name: digest((ROOT/name).read_bytes()) for name in paths}}
        manifest['restart_backend'] = any(item['path'].startswith('backend/') for item in manifest['files'])
        raw = json.dumps(manifest, indent=2).encode()
        info = tarfile.TarInfo('manifest.json'); info.size = len(raw)
        tar.addfile(info, io.BytesIO(raw))
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({'archive':str(archive), 'bytes':archive.stat().st_size, 'runtime_files':len(manifest['files'])}))


if __name__ == '__main__': main()
