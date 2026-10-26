from pathlib import Path

from tools.depgraph.extract import build_graph
from tools.depgraph.queries import duplicates, impact

ROOT = Path(__file__).resolve().parents[3]
G = build_graph(ROOT)


def test_graph_spans_every_layer():
    layers = {n.layer for n in G.nodes.values()}
    assert {"ui", "api", "schema", "db", "pipeline", "source", "warehouse", "infra", "config", "legacy", "test"} <= layers


def test_ui_client_resolves_to_real_routes():
    unresolved = [n for n in G.nodes.values() if n.attrs.get("unresolved") and n.layer == "api"]
    assert unresolved == [], [n.id for n in unresolved]


def test_cost_center_width_impact_reaches_all_layers():
    rep = impact(G, "cost_center_code", attr="width")
    layers = set(rep.by_layer())
    assert {"ui", "schema", "db", "pipeline", "warehouse", "infra", "legacy"} <= layers, layers
    assert all(s.attrs["width"] == 6 for s in rep.seeds)
    assert not rep.width_conflicts


def test_tax_id_normaliser_has_a_single_behaviour():
    groups = {d.concept: d for d in duplicates(G)}
    d = groups["normalize_tax_id"]
    assert not d.divergent, d.variants
    assert not any(m.id.startswith("legacy:") for m in d.members), [m.id for m in d.members]
