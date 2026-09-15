"""Targeted tracked/unignored-file credential pattern check, not a full secret audit."""
from pathlib import Path
import re
import subprocess

root=Path(__file__).resolve().parents[1]
paths=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=root).decode().split('\0')
patterns=[r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b', r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
          r'\bgh[pousr]_[A-Za-z0-9]{30,}\b', r'github_pat_[A-Za-z0-9_]{50,}']
findings=[]
for name in paths:
    if not name:continue
    p=root/name
    if p.is_file():
        content=p.read_text(errors='replace')
        if any(re.search(pattern,content) for pattern in patterns):findings.append(name)
if findings:raise SystemExit('Potential credential patterns in: '+', '.join(findings))
print('Targeted credential-pattern check: PASS (not proof that all secrets are absent)')
