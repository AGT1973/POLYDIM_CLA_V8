"""Rebuild and capture bounded, machine-readable validation results."""
import argparse, subprocess, sys, pathlib, json, platform, time, hashlib, shutil
p=argparse.ArgumentParser();p.add_argument('--scale',action='store_true');p.add_argument('--rust',action='store_true');p.add_argument('--sanitize',action='store_true');args=p.parse_args()
root=pathlib.Path(__file__).resolve().parents[1]
commands=[[sys.executable,'build.py']+(['--sanitize'] if args.sanitize else []),[sys.executable,'tests/test_regression.py'],[sys.executable,'tests/test_quantum.py']]
if args.scale:commands.append([sys.executable,'tests/test_scale.py'])
if args.rust:
 if not shutil.which('cargo'):raise SystemExit('Rust requested but cargo is unavailable')
 commands.append(['cargo','test'])
report={'platform':platform.platform(),'python':sys.version,'steps':[],'sanitized':args.sanitize,'rust_requested':args.rust}
failed=False
for index,cmd in enumerate(commands):
 start=time.perf_counter()
 try:
  proc=subprocess.run(cmd,cwd=root,text=True,capture_output=True,timeout=180)
  code=proc.returncode;output=proc.stdout+proc.stderr
 except subprocess.TimeoutExpired:
  code=124;output='Validation exceeded 180 seconds; process terminated.'
 log=root/'docs'/f'verify_{index}.txt';log.write_text(output,encoding='utf-8')
 report['steps'].append({'command':cmd[1:] if cmd[0]==sys.executable else cmd,'returncode':code,'seconds':time.perf_counter()-start,'log':log.name})
 if code:failed=True;break
report['status']='failed' if failed else 'passed'
report['source_sha256']={str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for folder in ('src','include','python','tests') for f in sorted((root/folder).rglob('*')) if f.is_file() and '__pycache__' not in f.parts}
(root/'docs'/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'status':report['status'],'steps':len(report['steps'])}))
sys.exit(1 if failed else 0)
