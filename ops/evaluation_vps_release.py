"""Explicit production-staging release helper; run on the verified VPS only.

Inspect is read-only. Apply keeps server-only backups, never downloads secrets.
Rollback restores only this release's files/env and the original frontend link.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tarfile

ROOTS = {'agent':Path('/var/www/agent-api'), 'backend':Path('/var/www/backend'),
         'analytics_frontend':Path('/var/www/analytics_frontend')}


def digest(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def target(name):
    relative = Path(name)
    root = ROOTS[relative.parts[0]]
    dest = root.joinpath(*relative.parts[1:])
    assert dest.resolve().is_relative_to(root.resolve()) and not dest.is_symlink()
    return dest


def env_update(path, values):
    text = path.read_text()
    for key, value in values.items():
        line = key + '=' + value
        if re.search(r'^' + key + r'=', text, flags=re.M):
            text = re.sub(r'^' + key + r'=.*$', line, text, flags=re.M)
        else: text = text.rstrip() + '\n' + line + '\n'
    temp = path.with_suffix('.evaluation-next')
    temp.write_text(text); temp.chmod(0o600); temp.replace(path)


def main():
    assert socket.gethostname() == 'momolita', 'Unexpected server; refusing deployment'
    mode, archive_path = sys.argv[1:3]
    archive = Path(archive_path)
    with tarfile.open(archive) as tar:
        manifest = json.load(tar.extractfile('manifest.json'))
    release = manifest['release']
    assert re.fullmatch(r'202[6-9][0-9]{4}-evaluation-m[0-9]+-[0-9]+', release)
    backup = Path('/var/backups/advertising-agent/evaluation') / release
    staging = Path('/var/www/evaluation-releases') / release
    if mode == 'preflight':
        sys.path.insert(0, str(ROOTS['agent']))
        from config import config
        from pymongo import MongoClient
        client = MongoClient(config.MONGODB_URI, serverSelectionTimeoutMS=5000)
        db = client[config.MONGODB_DB]
        active = {name: db[name].count_documents({'status': {'$in': ['running','queued']}})
                  for name in ['autopilot_runs','evaluation_investigation_jobs']}
        assert not any(active.values()), 'Active work exists; postpone restart'
        assert config.EVALUATION_MULTI_AGENT_ENABLED and not config.EVALUATION_WORKER_ENABLED
        assert config.EVALUATION_AGENT_MODEL == 'gpt-5.4-mini'
        print(json.dumps({'hostname':socket.gethostname(),'active_work':active,
                          'periodic_scheduler':False,'model':config.EVALUATION_AGENT_MODEL}))
        client.close()
        return
    if mode == 'verify':
        for item in manifest['files']:
            assert digest(target(item['path'])) == item['sha256'], item['path']
        for name, expected in manifest.get('runtime_snapshot', {}).items():
            assert digest(target(name)) == expected, name
        frontend = Path('/var/www/agent')
        assert frontend.resolve() == (staging/'frontend').resolve()
        for item in manifest['frontend_files']:
            assert hashlib.sha256((frontend/item['path']).read_bytes()).hexdigest() == item['sha256'], item['path']
        saved = json.loads((backup/'rollback.json').read_text())
        assert all((backup/'files'/name).is_file() for name in saved['existing'])
        assert (backup/'agent.env').is_file() and (backup/'backend.env').is_file()
        print(json.dumps({'release': release, 'runtime_files_verified': len(manifest['files']),
                          'full_runtime_snapshot_verified': len(manifest.get('runtime_snapshot', {})),
                          'frontend_files_verified': len(manifest['frontend_files']), 'rollback_backup_present': True}))
        return
    if mode == 'inspect':
        unknown = []
        for item in manifest['files']:
            dest = target(item['path'])
            current = digest(dest) if dest.is_file() else None
            if current and current not in item['known_previous'] + [item['sha256']]:
                unknown.append({'path':item['path'], 'deployed_sha256':current})
        print(json.dumps({'release':release, 'files':len(manifest['files']), 'unknown_remote_changes':unknown}))
        return
    if mode == 'rollback':
        saved = json.loads((backup/'rollback.json').read_text())
        subprocess.run(['pm2','stop','agent-api'],check=True)
        for name in saved['existing']:
            shutil.copy2(backup/'files'/name, target(name))
        for name in saved['new']:
            dest = target(name)
            if dest.exists():
                quarantine = backup/'rolled-back-new'/name
                quarantine.parent.mkdir(parents=True, exist_ok=True)
                dest.replace(quarantine)
        for key in ('agent','backend'):
            shutil.copy2(backup/(key+'.env'), ROOTS[key]/'.env')
        next_link = Path('/var/www/agent.evaluation-rollback')
        assert not next_link.exists() and not next_link.is_symlink()
        next_link.symlink_to(saved['frontend']); next_link.replace('/var/www/agent')
        if saved.get('restart_backend', True):
            subprocess.run(['pm2','restart','adspilot-api'],check=True)
        subprocess.run(['pm2','restart','agent-api'],check=True)
        print('rollback_complete', release)
        return
    assert mode == 'apply'
    assert not backup.exists() and not staging.exists(), 'Release already exists'
    assert Path('/var/www/agent').is_symlink(), 'Expected immutable frontend release link'
    if manifest.get('previous_release'):
        assert Path('/var/www/agent').resolve() == Path('/var/www/evaluation-releases')/manifest['previous_release']/'frontend'
    # Recheck immediately before modifying files, not only in a prior inspect.
    for item in manifest['files']:
        dest = target(item['path'])
        actual = digest(dest) if dest.is_file() else None
        if 'expected_previous' in item:
            assert actual == item['expected_previous'], 'Runtime drift: ' + item['path']
        else:
            assert actual is None or actual in item['known_previous'] + [item['sha256']], 'Unknown runtime: ' + item['path']
    staging.mkdir(parents=True)
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            path = staging/member.name
            assert path.resolve().is_relative_to(staging.resolve()) and member.isfile()
            assert not member.issym() and not member.islnk()
            path.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(member) as source, path.open('wb') as dest: shutil.copyfileobj(source,dest)
    for item in manifest['files']:
        assert digest(staging/item['path']) == item['sha256']
    for item in manifest['frontend_files']:
        dest = staging/'frontend'/item['path']
        assert dest.resolve().is_relative_to((staging/'frontend').resolve())
        if not dest.exists():
            previous = Path('/var/www/agent')/item['path']
            assert previous.is_file() and previous.resolve().is_relative_to(Path('/var/www/agent').resolve())
            dest.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(previous,dest)
        assert hashlib.sha256(dest.read_bytes()).hexdigest() == item['sha256']
    backup.mkdir(parents=True, mode=0o700)
    saved = {'frontend':os.readlink('/var/www/agent'), 'existing':[], 'new':[],
             'restart_backend': manifest.get('restart_backend', True)}
    for key in ('agent','backend'):
        shutil.copy2(ROOTS[key]/'.env', backup/(key+'.env'))
        (backup/(key+'.env')).chmod(0o600)
    for item in manifest['files']:
        name = item['path']; dest = target(name)
        if dest.is_file():
            copy = backup/'files'/name; copy.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(dest,copy); saved['existing'].append(name)
        else: saved['new'].append(name)
    (backup/'rollback.json').write_text(json.dumps(saved,indent=2))
    shutil.copy2(staging/'manifest.json',backup/'manifest.json')
    # All recovery artifacts exist before any active runtime file changes.
    subprocess.run(['pm2','stop','agent-api'],check=True)
    try:
        for item in manifest['files']:
            dest=target(item['path']); dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(staging/item['path'],dest); dest.chmod(0o644)
        if not manifest.get('preserve_environment'):
            key = secrets.token_hex(32)
            env_update(ROOTS['backend']/'.env', {'REPORT_INTERNAL_API_KEY':key})
            env_update(ROOTS['agent']/'.env', {'REPORT_INTERNAL_API_KEY':key,
                       'EVALUATION_MULTI_AGENT_ENABLED':'true', 'EVALUATION_WORKER_ENABLED':'false',
                       'EVALUATION_AGENT_MODEL':'gpt-5.4-mini'})
        subprocess.run(['node','--check','server.js'],cwd=ROOTS['backend'],check=True)
        subprocess.run([str(ROOTS['agent']/'venv/bin/python'),'-m','compileall','-q','evaluation','main.py'],cwd=ROOTS['agent'],check=True)
        if manifest.get('restart_backend', True):
            subprocess.run(['pm2','restart','adspilot-api'],check=True)
        subprocess.run(['pm2','restart','agent-api'],check=True)
        next_link=Path('/var/www/agent.evaluation-next')
        assert not next_link.exists() and not next_link.is_symlink()
        for p in (staging/'frontend').rglob('*'): p.chmod(0o755 if p.is_dir() else 0o644)
        next_link.symlink_to(staging/'frontend'); next_link.replace('/var/www/agent')
        print(json.dumps({'release':release,'backup':str(backup),'frontend':str(staging/'frontend')}))
    except Exception:
        print('Deployment failed; rollback artifacts:',backup)
        raise


if __name__ == '__main__': main()
