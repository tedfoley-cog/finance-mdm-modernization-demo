"""Questions the graph answers: impact of a change, duplicated logic, environment drift."""

from __future__ import annotations

import re
import subprocess
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from .model import LAYER_ORDER, Graph, Node

CONTAINMENT = {"has-column", "has-field", "has-expectation"}


def _norm(s: str) -> str:
    """camelCase / UPPER_SNAKE / dotted → lower snake, so cost_center_code == costCenterCode == COST_CENTER_CODE."""
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    return "_".join(t for t in re.split(r"[^a-zA-Z0-9]+", s.lower()) if t)


def _tokens(s: str) -> set[str]:
    return set(_norm(s).split("_")) - {""}


@dataclass
class ImpactHit:
    node: Node
    depth: int
    via: str  # edge kind that pulled it in, or "match"
    from_id: str | None


@dataclass
class ImpactReport:
    term: str
    seeds: list[Node]
    hits: list[ImpactHit]
    width_conflicts: list[Node] = field(default_factory=list)

    def by_layer(self) -> dict[str, list[ImpactHit]]:
        out: dict[str, list[ImpactHit]] = {}
        for h in sorted(
            self.hits, key=lambda h: (LAYER_ORDER.index(h.node.layer) if h.node.layer in LAYER_ORDER else 99, h.depth, h.node.id)
        ):
            out.setdefault(h.node.layer, []).append(h)
        return out


def impact(g: Graph, term: str, depth: int = 2, attr: str | None = None) -> ImpactReport:
    """Seed with every node whose name/attrs mention the term (token-aware: cost_center_code == costCenterCode ==
    COST_CENTER_CODE), then walk edges `depth` hops in both directions. `attr` (e.g. 'width') restricts the
    seeds to nodes carrying that attribute, which is what a 'widen this field' question needs."""
    want = _norm(term)
    seeds = []
    for n in g.nodes.values():
        hay = [_norm(n.name)] + [_norm(str(v)) for k, v in n.attrs.items() if k in {"concept", "args", "env_var"} and v]
        if any(want in h for h in hay) and (attr is None or n.attrs.get(attr) is not None):
            seeds.append(n)
    hits: dict[str, ImpactHit] = {s.id: ImpactHit(s, 0, "match", None) for s in seeds}
    q = deque((s.id, 0) for s in seeds)
    while q:
        nid, d = q.popleft()
        if d >= depth:
            continue
        for e, other in g.neighbours(nid):
            if e.kind in CONTAINMENT and e.src == nid:
                continue  # never fan out from a table to its unrelated sibling columns
            if other not in hits:
                hits[other] = ImpactHit(g.nodes[other], d + 1, e.kind, nid)
                q.append((other, d + 1))
    rep = ImpactReport(term, seeds, list(hits.values()))
    if attr == "width":
        widths = {}
        for s in seeds:
            widths.setdefault(s.attrs.get("width"), []).append(s)
        if len(widths) > 1:
            rep.width_conflicts = [n for w, ns in widths.items() for n in ns]
    return rep


@dataclass
class DupeGroup:
    concept: str
    members: list[Node]
    variants: dict[str, list[str]]  # regex/behaviour variant -> node ids

    @property
    def divergent(self) -> bool:
        return len(self.variants) > 1


def _regex_signature(rx: str) -> str:
    """Fold dialect spelling so the Python, JS and Snowflake spellings of the same character class compare equal."""
    rx = rx.replace("\\\\", "\\").replace("[[:space:]]", "\\s").replace("[:space:]", "\\s")
    rx = re.sub(r"\\\.", ".", rx)
    return rx


def duplicates(g: Graph) -> list[DupeGroup]:
    """Functions/constants that implement the same concept in more than one place. Membership is explicit
    ('mirrors' edges) plus name-token overlap; divergence is judged on the regex/behaviour attribute."""
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        while parent.setdefault(x, x) != x:
            x = parent[x]
        return x

    for e in g.edges:
        if e.kind == "mirrors":
            parent[find(e.src)] = find(e.dst)
    groups: dict[str, set[str]] = {}
    for nid in list(parent):
        groups.setdefault(find(nid), set()).add(nid)
    # width constants are a second family: everything carrying a width for the cost center code
    cc = [
        n.id
        for n in g.nodes.values()
        if n.attrs.get("width") and ("cost_center_code" in _norm(n.name) or "cost_center_code" in _norm(str(n.attrs.get("concept", ""))))
    ]
    if cc:
        groups["concept:cost_center_code_width"] = set(cc)
    out = []
    for concept, ids in groups.items():
        members = [g.nodes[i] for i in sorted(ids)]
        variants: dict[str, list[str]] = {}
        for m in members:
            key = _regex_signature(str(m.attrs.get("regex") or m.attrs.get("width") or "?"))
            variants.setdefault(key, []).append(m.id)
        name = g.nodes[concept].name if concept in g.nodes else concept.split(":")[-1]
        out.append(DupeGroup(name, members, variants))
    return sorted(out, key=lambda d: (-len(d.variants), d.concept))


@dataclass
class DriftReport:
    base: str
    env: str
    files: list[tuple[str, str]]  # (status, path)
    touched_nodes: list[Node]
    tfvars_only: list[str]  # files that differ but are env config, not code
    commits_ahead: list[str]


def drift(g: Graph, root: Path, env_branch: str, base: str = "main") -> DriftReport:
    """What is different between an environment branch and main, mapped back to graph nodes."""

    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False).stdout

    files = [tuple(line.split("\t", 1)) for line in git("diff", "--name-status", f"{base}...{env_branch}").splitlines() if "\t" in line]
    ahead = [line for line in git("log", "--oneline", f"{base}..{env_branch}").splitlines()]
    paths = {p for _, p in files}
    touched = sorted({n.id: n for n in g.nodes.values() if n.path in paths}.values(), key=lambda n: n.id)
    tfvars = sorted(p for p in paths if p.endswith(".tfvars"))
    return DriftReport(base, env_branch, files, touched, tfvars, ahead)


def env_values(g: Graph, var: str) -> dict[str, str]:
    node = g.nodes.get(f"infra:var.{var}")
    return (node.attrs.get("per_env") if node else None) or {}
