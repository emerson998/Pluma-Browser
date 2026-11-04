"""Measure the whole browser process tree; psutil is imported only by this command."""
import argparse
import json
import statistics
import time
import psutil

parser = argparse.ArgumentParser()
parser.add_argument('pid', type=int)
parser.add_argument('--seconds', type=int, default=60)
parser.add_argument('--label', default='browser')
parser.add_argument('--output')
args = parser.parse_args()
if not 1 <= args.seconds <= 3600:
    parser.error('seconds must be between 1 and 3600')
root = psutil.Process(args.pid)
samples = []
known = {}
for _ in range(args.seconds):
    try:
        processes = [root] + root.children(recursive=True)
    except psutil.NoSuchProcess:
        break
    for process in processes:
        if process.pid not in known:
            known[process.pid] = process
            process.cpu_percent()
    time.sleep(1)
    rss = uss = cpu = 0
    for process in processes:
        try:
            rss += process.memory_info().rss
            cpu += known[process.pid].cpu_percent()
            uss += getattr(process.memory_full_info(), 'uss', 0)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    samples.append({'rss_mb': round(rss / 1048576, 2), 'uss_mb': round(uss / 1048576, 2),
                    'cpu_percent': round(cpu, 2), 'processes': len(processes)})
if not samples:
    raise SystemExit('Browser exited before sampling.')
result = {'label': args.label, 'samples': len(samples),
          'median_rss_mb': statistics.median(x['rss_mb'] for x in samples),
          'peak_rss_mb': max(x['rss_mb'] for x in samples),
          'median_uss_mb': statistics.median(x['uss_mb'] for x in samples),
          'median_cpu_percent': statistics.median(x['cpu_percent'] for x in samples),
          'note': 'RSS may count shared pages twice. CPU may exceed 100% on multiple cores.',
          'raw': samples}
text = json.dumps(result, indent=2)
print(text)
if args.output:
    from pathlib import Path
    Path(args.output).write_text(text, encoding='utf-8')
