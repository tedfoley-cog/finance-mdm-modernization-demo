"""Graph model shared by the extractors, the queries and the report."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

LAYER_ORDER = ["ui", "api", "schema", "db", "pipeline", "source", "warehouse", "infra", "config", "legacy", "test"]


@dataclass
class Node:
    id: str  # layer:name, e.g. "warehouse:FDP_MDM.CURATED.DIM_COST_CENTER"
    layer: str
    kind: str  # component, route, table, column, job, function, constant, resource, variable ...
    name: str
    path: str
    line: int = 0
    attrs: dict = field(default_factory=dict)  # width, env, dialect, values ...


@dataclass
class Edge:
    src: str
    dst: str
    kind: str  # calls, reads, writes, defines, configures, deploys, validates, implements, mirrors
    path: str = ""
    line: int = 0


class Graph:
    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []
        self._out: dict[str, list[Edge]] = defaultdict(list)
        self._in: dict[str, list[Edge]] = defaultdict(list)

    def add_node(self, node: Node) -> Node:
        existing = self.nodes.get(node.id)
        if existing:
            existing.attrs.update({k: v for k, v in node.attrs.items() if v is not None})
            return existing
        self.nodes[node.id] = node
        return node

    def add_edge(self, src: str, dst: str, kind: str, path: str = "", line: int = 0) -> None:
        if src == dst:
            return
        for e in self._out[src]:
            if e.dst == dst and e.kind == kind:
                return
        e = Edge(src, dst, kind, path, line)
        self.edges.append(e)
        self._out[src].append(e)
        self._in[dst].append(e)

    def out_edges(self, node_id: str) -> list[Edge]:
        return self._out.get(node_id, [])

    def in_edges(self, node_id: str) -> list[Edge]:
        return self._in.get(node_id, [])

    def neighbours(self, node_id: str) -> list[tuple[Edge, str]]:
        return [(e, e.dst) for e in self.out_edges(node_id)] + [(e, e.src) for e in self.in_edges(node_id)]

    def finalize(self) -> None:
        """Create placeholder nodes for dangling edge endpoints so queries never fall off the graph."""
        for e in self.edges:
            for nid in (e.src, e.dst):
                if nid not in self.nodes:
                    layer, _, name = nid.partition(":")
                    self.nodes[nid] = Node(id=nid, layer=layer, kind="external", name=name, path="", attrs={"unresolved": True})

    def to_json(self) -> str:
        payload = {
            "nodes": [asdict(n) for n in sorted(self.nodes.values(), key=lambda n: n.id)],
            "edges": [asdict(e) for e in sorted(self.edges, key=lambda e: (e.src, e.dst, e.kind))],
        }
        return json.dumps(payload, indent=1, sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> Graph:
        data = json.loads(text)
        g = cls()
        for n in data["nodes"]:
            g.add_node(Node(**n))
        for e in data["edges"]:
            g.add_edge(**e)
        return g

    @classmethod
    def load(cls, path: Path) -> Graph:
        return cls.from_json(path.read_text())
