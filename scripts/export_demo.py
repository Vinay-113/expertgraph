"""Record actual local responses; never represent a static replay as live inference."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
METHODS = ['bm25', 'semantic', 'graph', 'fixed_hybrid', 'bm25_semantic', 'routed_hybrid']
SAMPLES = [
    ('config', 'Configuration failure', 'Giving pytest a nonexistent config path either does nothing or raises FileNotFoundError depending on the extension. Which report covers both cases?'),
    ('retry', 'Linked issue evidence', 'Find reports explicitly linked to psf/requests#7601 about retries or HTTPAdapter.'),
    ('python', 'Installer checksum', 'A Windows Python 3.14t installer changed but its checksum stayed the same, causing CI installation to fail.'),
    ('unknown', 'Absent exact identifier', 'Find the HTTP error report containing GALAXY_HTTP_5K82P.'),
    ('action', 'Unsupported action', 'Patch my production Requests proxy configuration now and prove that the incident is resolved.'),
    ('ood', 'Out-of-domain question', 'What ingredients are used in a chocolate cake?'),
]


def main():
    with urlopen('http://127.0.0.1:8765/api/health', timeout=10) as response:
        if json.load(response)['documents'] != 109:
            raise ValueError('Unexpected demo corpus')
    examples = []
    for key, label, query in SAMPLES:
        recorded = {}
        for method in METHODS:
            request = Request('http://127.0.0.1:8765/api/query',
                              data=json.dumps({'query': query, 'method': method}).encode(),
                              headers={'Content-Type': 'application/json'})
            with urlopen(request, timeout=60) as response:
                report = json.load(response)
            # No full report bodies, source quotes or unstable latency measurements in public replay.
            for item in report['evidence'] + report.get('graph_neighbors', []):
                item.pop('quote', None)
            report.pop('timings_ms', None)
            recorded[method] = report
        examples.append({'id': key, 'label': label, 'query': query, 'reports': recorded})
        print(f'Recorded {label}: six methods', flush=True)
    result_path = ROOT / 'artifacts/validation-v1/results.json'
    pilot_path = ROOT / 'artifacts/results/results.json'
    output = {'mode': 'recorded_replay_not_live_inference',
              'recorded_at': datetime.now(timezone.utc).isoformat(),
              'validation_sha256': hashlib.sha256(result_path.read_bytes()).hexdigest(),
              'pilot_sha256': hashlib.sha256(pilot_path.read_bytes()).hexdigest(),
              'pilot': json.loads(pilot_path.read_text()),
              'validation': json.loads(result_path.read_text()), 'examples': examples}
    path = ROOT / 'docs/demo/recordings.json'
    path.write_text(json.dumps(output, indent=2) + '\n')
    print(f'Saved {len(examples) * len(METHODS)} recorded responses')


if __name__ == '__main__':
    main()
