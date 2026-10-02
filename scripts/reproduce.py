"""Replay in a new directory, without overwriting the published experiment."""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New, nonexistent experiment directory')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error('Output already exists; choose a new directory to preserve its contents.')
    output.mkdir(parents=True)
    for name in ('benchmark.draft.json', 'benchmark.challenge.v1.json', 'splits.json'):
        destination = output / 'data' / name
        destination.parent.mkdir(exist_ok=True)
        shutil.copyfile(ROOT / 'data' / name, destination)
    manifest = output / 'artifacts/results/corpus_manifest.json'
    manifest.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / 'artifacts/results/corpus_manifest.json', manifest)
    # The author's local verified corpus can be reused; never distribute it implicitly.
    if (ROOT / 'data/corpus.jsonl').exists():
        shutil.copyfile(ROOT / 'data/corpus.jsonl', output / 'data/corpus.jsonl')
        shutil.copyfile(ROOT / 'data/manifest.json', output / 'data/manifest.json')
    shutil.copytree(ROOT / 'ui', output / 'ui')
    for command in ('restore', 'evaluate', 'validate'):
        subprocess.run([sys.executable, str(ROOT / 'run_expertgraph.py'), '--root', str(output), command], check=True)
    print(f'Replay saved separately at {output}. Compare metrics; timings and serialized model hashes may differ.')


if __name__ == '__main__':
    main()
