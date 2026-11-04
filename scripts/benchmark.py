"""Sample parent + Chromium child RSS. Run against a Pluma/Chrome PID."""
import argparse
import json
import time
import statistics
import psutil

parser = argparse.ArgumentParser()
parser.add_argument('pid', type=int)
parser.add_argument('--seconds', type=int, default=60)
args = parser.parse_args()
parent = psutil.Process(args.pid)
samples = []
for _ in range(args.seconds):
    rss = 0
    for process in [parent] + parent.children(recursive=True):
        try:
            rss += process.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    samples.append(rss / 1024**2)
    time.sleep(1)
print(json.dumps({'samples': len(samples), 'median_rss_mb': round(statistics.median(samples), 1),
                  'peak_rss_mb': round(max(samples), 1),
                  'note': 'Sum of RSS can double-count shared pages; compare identical conditions.'}, indent=2))
