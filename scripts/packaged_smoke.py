import json
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
exe = root / 'dist/Pluma' / ('Pluma.exe' if os.name == 'nt' else 'Pluma')
with tempfile.TemporaryDirectory() as folder:
    report = Path(folder) / 'result.json'
    result = subprocess.run([str(exe), '--self-test', str(report)], timeout=60)
    assert result.returncode == 0, f'Package exit status {result.returncode}'
    assert report.exists(), 'Packaged executable did not write its test report'
    data = json.loads(report.read_text())
    assert data['success'], data
    print('PASS: packaged executable', data['checks'])
