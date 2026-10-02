"""Offline contract checks for the public recorded demo; no model download."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    data = json.loads((ROOT / 'docs/demo/recordings.json').read_text())
    assert data['mode'] == 'recorded_replay_not_live_inference'
    for key, path in [('pilot', 'artifacts/results/results.json'),
                      ('validation', 'artifacts/validation-v1/results.json')]:
        raw = (ROOT / path).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == data[key + '_sha256']
        assert json.loads(raw) == data[key]
    methods = set(data['validation']['methods'])
    assert len(data['examples']) == 6
    for example in data['examples']:
        assert set(example['reports']) == methods
        for method, report in example['reports'].items():
            assert report['query'] == example['query'] and report['method'] == method
            assert abs(sum(report['expert_weights'].values()) - 1) < 1e-6
            for item in report['evidence'] + report['graph_neighbors']:
                repo, number = item['id'].split('#')
                assert item['url'] == f'https://github.com/{repo}/issues/{number}'
                assert 'quote' not in item
            if example['id'] in ('unknown', 'action'):
                assert report['status'] == 'abstained' and report['scope_checks']
    assert next(x for x in data['examples'] if x['id'] == 'ood')['reports']['routed_hybrid']['status'] == 'abstained'
    print('Public replay: 36 responses, source identities, guard cases and artifact hashes verified')


if __name__ == '__main__':
    main()
