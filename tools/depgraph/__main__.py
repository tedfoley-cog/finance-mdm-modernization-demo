"""LedgerCore cross-stack dependency graph.

python -m tools.depgraph build [--check]               write depgraph/graph.json (or fail if stale)
python -m tools.depgraph impact <term> [--attr width] [--depth 2] [--html out.html]
python -m tools.depgraph dupes
python -m tools.depgraph drift env/qa env/prod
python -m tools.depgraph report out.html [--impact term]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .extract import build_graph
from .model import Graph
from .queries import drift, duplicates, env_values, impact
from .report import LAYER_LABEL, render

ROOT = Path(__file__).resolve().parents[2]
GRAPH_PATH = ROOT / "depgraph" / "graph.json"


def _graph(args) -> Graph:
    if getattr(args, "rebuild", False) or not GRAPH_PATH.exists():
        return build_graph(ROOT)
    return Graph.load(GRAPH_PATH)


def cmd_build(args) -> int:
    g = build_graph(ROOT)
    text = g.to_json()
    if args.check:
        if not GRAPH_PATH.exists() or GRAPH_PATH.read_text() != text:
            print("depgraph/graph.json is stale: run `python -m tools.depgraph build` and commit the result", file=sys.stderr)
            return 1
        print(f"depgraph up to date ({len(g.nodes)} nodes, {len(g.edges)} edges)")
        return 0
    GRAPH_PATH.parent.mkdir(exist_ok=True)
    GRAPH_PATH.write_text(text)
    print(f"wrote {GRAPH_PATH.relative_to(ROOT)} ({len(g.nodes)} nodes, {len(g.edges)} edges)")
    return 0


def cmd_impact(args) -> int:
    g = _graph(args)
    rep = impact(g, args.term, depth=args.depth, attr=args.attr)
    print(f"impact of '{args.term}': {len(rep.seeds)} direct matches, {len(rep.hits)} nodes within {args.depth} hops\n")
    for layer, hits in rep.by_layer().items():
        print(f"[{LAYER_LABEL.get(layer, layer)}]")
        for h in hits:
            attrs = " ".join(f"{k}={v}" for k, v in h.node.attrs.items() if v is not None and k not in {"per_env", "unresolved"})
            mark = "*" if h.depth == 0 else " "
            print(f" {mark} {h.node.name:58} {h.node.kind:14} {h.node.path}:{h.node.line}  {attrs}")
        print()
    if rep.width_conflicts:
        print("WIDTH MISMATCH between: " + ", ".join(f"{n.name}={n.attrs.get('width')}" for n in rep.width_conflicts))
    per_env = env_values(g, "cost_center_code_width") if "cost" in args.term.lower() else {}
    if per_env:
        print("per-environment tfvars: " + ", ".join(f"{k}={v}" for k, v in per_env.items()))
    if args.html:
        Path(args.html).write_text(render(g, impact=rep, dupes=duplicates(g)))
        print(f"\nhtml report: {args.html}")
    return 0


def cmd_dupes(args) -> int:
    g = _graph(args)
    for d in duplicates(g):
        flag = "DIVERGENT" if d.divergent else "consistent"
        print(f"{d.concept}: {len(d.members)} copies, {len(d.variants)} variant(s) [{flag}]")
        for variant, ids in d.variants.items():
            print(f"    {variant}")
            for i in ids:
                n = g.nodes[i]
                print(f"        {n.id:60} {n.path}:{n.line}")
        print()
    return 0


def cmd_drift(args) -> int:
    g = _graph(args)
    for env in args.envs:
        dr = drift(g, ROOT, env, base=args.base)
        print(f"== {env} vs {args.base}: {len(dr.commits_ahead)} commit(s) not on {args.base}")
        for c in dr.commits_ahead:
            print(f"   {c}")
        for status, path in dr.files:
            ns = [n.id for n in dr.touched_nodes if n.path == path]
            label = ", ".join(ns) if ns else ("new file, not on main" if status == "A" else "config only")
            print(f"   {status:2} {path:55} {label}")
        print()
    return 0


def cmd_report(args) -> int:
    g = _graph(args)
    rep = impact(g, args.impact, attr=args.attr) if args.impact else None
    drifts = [drift(g, ROOT, e) for e in args.drift] if args.drift else None
    Path(args.out).write_text(render(g, impact=rep, dupes=duplicates(g), drifts=drifts))
    print(f"wrote {args.out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="depgraph", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rebuild", action="store_true", help="scan the tree instead of reading depgraph/graph.json")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--check", action="store_true")
    b.set_defaults(fn=cmd_build)
    i = sub.add_parser("impact")
    i.add_argument("term")
    i.add_argument("--attr")
    i.add_argument("--depth", type=int, default=2)
    i.add_argument("--html")
    i.set_defaults(fn=cmd_impact)
    d = sub.add_parser("dupes")
    d.set_defaults(fn=cmd_dupes)
    dr = sub.add_parser("drift")
    dr.add_argument("envs", nargs="+")
    dr.add_argument("--base", default="main")
    dr.set_defaults(fn=cmd_drift)
    r = sub.add_parser("report")
    r.add_argument("out")
    r.add_argument("--impact")
    r.add_argument("--attr")
    r.add_argument("--drift", nargs="*")
    r.set_defaults(fn=cmd_report)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
