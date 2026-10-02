from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="ExpertGraph research prototype")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Project directory containing data/")
    sub = parser.add_subparsers(dest="command", required=True)
    collect = sub.add_parser("collect", help="Collect public GitHub incident reports")
    collect.add_argument("--per-repo", type=int, default=40)
    sub.add_parser("restore", help="Restore the frozen public IDs, verifying the corpus hash")
    sub.add_parser("prepare", help="Freeze incident components and generate silver queries")
    sub.add_parser("evaluate", help="Train router, calibrate on dev, evaluate held-out pilot")
    sub.add_parser("validate", help="Run frozen-model stress diagnostics without replacing the pilot")
    query = sub.add_parser("query", help="Retrieve source evidence with the trained router")
    query.add_argument("text")
    query.add_argument("--method", choices=["bm25", "semantic", "graph", "fixed_hybrid", "bm25_semantic", "routed_hybrid"], default="routed_hybrid")
    serve = sub.add_parser("serve", help="Start local evidence explorer")
    serve.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.command == "collect":
        from .data import GitHubCollector
        docs = GitHubCollector(root).collect(args.per_repo)
        print(f"Collected {len(docs)} public issue reports")
    elif args.command == "restore":
        from .data import GitHubCollector
        docs = GitHubCollector(root).restore(root / "artifacts/results/corpus_manifest.json")
        print(f"Verified {len(docs)} frozen incident reports")
    elif args.command == "prepare":
        from .data import load_jsonl
        from .benchmark import prepare
        split = prepare(root, load_jsonl(root / "data/corpus.jsonl"))
        from collections import Counter
        print(json.dumps(dict(Counter(split.values())), indent=2))
    elif args.command == "evaluate":
        from .evaluate import run
        result = run(root)
        print(json.dumps(result["pilot"], indent=2))
    elif args.command == "validate":
        from .validation import run
        result = run(root)
        print(json.dumps(result["challenge"], indent=2))
    else:
        from .server import load_system, serve
        engine, router, calibrator = load_system(root)
        if args.command == "query":
            print(json.dumps(engine.report(args.text, router, calibrator, method=args.method), indent=2))
        else:
            serve(root, engine, router, calibrator, args.port)


if __name__ == "__main__":
    main()
