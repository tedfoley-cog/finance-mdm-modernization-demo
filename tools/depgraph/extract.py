"""Deterministic extractors: one per technology, all regex/AST based, no network, no runtime import of app code.

Node id convention: "<layer>:<name>". Names are stable identifiers (route path, table name, function name,
Terraform address) so the same thing referenced from several places collapses onto one node.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import yaml

from .model import Graph, Node

SNOWFLAKE_OBJ = re.compile(r"\bFDP_MDM\.(LANDING|CURATED|CONSUMPTION|UTIL)\.([A-Z_][A-Z0-9_]*)", re.IGNORECASE)
VARCHAR_COL = re.compile(r"^\s*([A-Z_][A-Z0-9_]*)\s+VARCHAR\((\d+)\)", re.IGNORECASE | re.MULTILINE)


def _rel(root: Path, p: Path) -> str:
    return p.relative_to(root).as_posix()


def _lineno(text: str, idx: int) -> int:
    return text.count("\n", 0, idx) + 1


# ---------------------------------------------------------------------------------------------- API
def extract_api(root: Path, g: Graph) -> None:
    models_path = root / "api/app/models.py"
    tree = ast.parse(models_path.read_text())
    class_to_table: dict[str, str] = {}
    for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
        table = None
        for stmt in cls.body:
            if isinstance(stmt, ast.Assign) and any(getattr(t, "id", "") == "__tablename__" for t in stmt.targets):
                table = stmt.value.value
        if not table:
            continue
        class_to_table[cls.name] = table
        tid = f"db:{table}"
        g.add_node(Node(tid, "db", "table", table, _rel(root, models_path), cls.lineno, {"engine": "postgres/rds"}))
        g.add_edge(f"api:models.{cls.name}", tid, "defines", _rel(root, models_path), cls.lineno)
        g.add_node(Node(f"api:models.{cls.name}", "api", "orm-model", cls.name, _rel(root, models_path), cls.lineno))
        for stmt in cls.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.value, ast.Call):
                col = stmt.target.id
                width = None
                for a in stmt.value.args:
                    if isinstance(a, ast.Call) and getattr(a.func, "id", "") == "String" and a.args:
                        width = a.args[0].value
                cid = f"db:{table}.{col}"
                g.add_node(
                    Node(cid, "db", "column", f"{table}.{col}", _rel(root, models_path), stmt.lineno, {"width": width} if width else {})
                )
                g.add_edge(tid, cid, "has-column")

    # routers: prefix + decorators + model references in the function body
    for rp in sorted((root / "api/app/routers").glob("*.py")):
        text = rp.read_text()
        m = re.search(r'APIRouter\(prefix="([^"]+)"', text)
        if not m:
            continue
        prefix = m.group(1)
        rtree = ast.parse(text)
        for fn in [n for n in rtree.body if isinstance(n, ast.FunctionDef)]:
            for dec in fn.decorator_list:
                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.func.attr in {"get", "post", "put", "delete"}:
                    method = dec.func.attr.upper()
                    route = prefix + (dec.args[0].value if dec.args else "")
                    rid = f"api:{method} {route}"
                    g.add_node(Node(rid, "api", "route", f"{method} {route}", _rel(root, rp), fn.lineno, {"handler": fn.name}))
                    body_src = ast.get_source_segment(text, fn) or ""
                    for cls, table in class_to_table.items():
                        if re.search(rf"\bmodels\.{cls}\b", body_src):
                            g.add_edge(rid, f"db:{table}", "writes" if method in {"POST", "PUT"} else "reads", _rel(root, rp), fn.lineno)
                    for sm in re.finditer(r"\bschemas\.(\w+)", body_src):
                        g.add_edge(rid, f"schema:{sm.group(1)}", "validates", _rel(root, rp), fn.lineno)
                    for svc in re.finditer(r"\b(change_requests|svc|publish)\.(\w+)\(", body_src):
                        g.add_edge(rid, f"api:services.{svc.group(2)}", "calls", _rel(root, rp), fn.lineno)

    # services
    for sp in sorted((root / "api/app/services").glob("*.py")):
        text = sp.read_text()
        stree = ast.parse(text)
        for fn in [n for n in stree.body if isinstance(n, ast.FunctionDef)]:
            sid = f"api:services.{fn.name}"
            g.add_node(Node(sid, "api", "service", fn.name, _rel(root, sp), fn.lineno))
            src = ast.get_source_segment(text, fn) or ""
            for cls, table in class_to_table.items():
                if re.search(rf"\bmodels\.{cls}\b", src):
                    g.add_edge(sid, f"db:{table}", "writes", _rel(root, sp), fn.lineno)
            if "boto3" in src or "s3" in src.lower():
                g.add_edge(sid, "infra:aws_s3_bucket.publish", "writes", _rel(root, sp), fn.lineno)

    # schemas (pydantic constraints) and validators
    sp = root / "api/app/schemas.py"
    text = sp.read_text()
    stree = ast.parse(text)
    for cls in [n for n in stree.body if isinstance(n, ast.ClassDef)]:
        sid = f"schema:{cls.name}"
        g.add_node(Node(sid, "schema", "pydantic-model", cls.name, _rel(root, sp), cls.lineno))
        for base in cls.bases:
            if isinstance(base, ast.Name) and base.id != "BaseModel":
                g.add_edge(sid, f"schema:{base.id}", "extends", _rel(root, sp), cls.lineno)
        for stmt in cls.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.value, ast.Call) and getattr(stmt.value.func, "id", "") == "Field":
                kw = {k.arg: getattr(k.value, "value", None) for k in stmt.value.keywords}
                if "max_length" in kw:
                    fid = f"schema:{cls.name}.{stmt.target.id}"
                    g.add_node(
                        Node(
                            fid,
                            "schema",
                            "field",
                            f"{cls.name}.{stmt.target.id}",
                            _rel(root, sp),
                            stmt.lineno,
                            {"width": kw["max_length"], "min_length": kw.get("min_length")},
                        )
                    )
                    g.add_edge(sid, fid, "has-field")
        src = ast.get_source_segment(text, cls) or ""
        for vm in re.finditer(r"validators\.(\w+)\(", src):
            g.add_edge(sid, f"api:validators.{vm.group(1)}", "calls", _rel(root, sp), cls.lineno)

    vp = root / "api/app/validators.py"
    text = vp.read_text()
    vtree = ast.parse(text)
    for node in vtree.body:
        if isinstance(node, ast.FunctionDef):
            g.add_node(
                Node(
                    f"api:validators.{node.name}",
                    "api",
                    "function",
                    node.name,
                    _rel(root, vp),
                    node.lineno,
                    {"regex": _first_regex(ast.get_source_segment(text, node) or "")},
                )
            )
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and "compile" in ast.dump(node.value.func):
            name = node.targets[0].id
            g.add_node(
                Node(
                    f"api:validators.{name}",
                    "api",
                    "constant",
                    name,
                    _rel(root, vp),
                    node.lineno,
                    {"regex": _first_regex(ast.get_source_segment(text, node) or "")},
                )
            )
    _inherit_constant_regex(g, vtree, text, "api:validators.", _rel(root, vp))

    # alembic migrations
    for mp in sorted((root / "api/alembic/versions").glob("*.py")):
        text = mp.read_text()
        mid = f"db:migration/{mp.stem}"
        g.add_node(Node(mid, "db", "migration", mp.stem, _rel(root, mp), 1))
        for m in re.finditer(r'op\.(create_table|add_column|alter_column|drop_column)\(\s*"(\w+)"', text):
            g.add_edge(mid, f"db:{m.group(2)}", m.group(1), _rel(root, mp), _lineno(text, m.start()))


def _inherit_constant_regex(g: Graph, tree: ast.Module, text: str, prefix: str, path: str) -> None:
    """A function whose body uses a module-level compiled regex inherits that regex as its behaviour signature."""
    consts = {
        n.targets[0].id: _first_regex(ast.get_source_segment(text, n) or "")
        for n in tree.body
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call) and "compile" in ast.dump(n.value.func)
    }
    for fn in [n for n in tree.body if isinstance(n, ast.FunctionDef)]:
        src = ast.get_source_segment(text, fn) or ""
        node = g.nodes.get(f"{prefix}{fn.name}")
        for const, regex in consts.items():
            if re.search(rf"\b{const}\b", src) and node is not None:
                if f"{prefix}{const}" in g.nodes:
                    g.add_edge(node.id, f"{prefix}{const}", "uses", path, fn.lineno)
                if not node.attrs.get("regex") and regex:
                    node.attrs["regex"] = regex


def _first_regex(src: str) -> str | None:
    m = re.search(r"re\.compile\(\s*r?\"([^\"]+)\"", src) or re.search(r"re\.fullmatch\(\s*r?\"([^\"]+)\"", src)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------------------------- UI
def _route_index(g: Graph) -> dict[str, str]:
    """'GET /api/x/{a}/{b}' -> node id, keyed with path params folded to '{}' so callers can match positionally."""
    return {re.sub(r"\{[^}]+\}", "{}", n.name): n.id for n in g.nodes.values() if n.layer == "api" and n.kind == "route"}


def _strip_interpolations(line: str) -> str:
    """Replace every `${...}` (brace-balanced) in a TS template string with '{}'."""
    out, i = [], 0
    while i < len(line):
        if line.startswith("${", i):
            depth, j = 1, i + 2
            while j < len(line) and depth:
                depth += {"{": 1, "}": -1}.get(line[j], 0)
                j += 1
            out.append("{}")
            i = j
        else:
            out.append(line[i])
            i += 1
    return "".join(out)


def extract_ui(root: Path, g: Graph) -> None:
    client = root / "web/src/api/client.ts"
    if not client.exists():
        return
    text = client.read_text()
    base = "/api"
    routes = _route_index(g)
    for m in re.finditer(r"^\s*(\w+): \(.*?\) => http<[^>]+>\((.*)$", text, re.MULTILINE):
        name, rest = m.group(1), _strip_interpolations(m.group(2))
        pm = re.match(r"\s*[`'](.*?)[`']", rest)
        mm = re.search(r"method:\s*'(\w+)'", rest)
        if not pm:
            continue
        method = mm.group(1) if mm else "GET"
        path = re.sub(r"(?<!/)\{\}$", "", pm.group(1).split("?")[0]).rstrip("/")  # trailing `${query}` is not a path segment
        route_id = routes.get(f"{method} {base}{path}", f"api:{method} {base}{path}")
        fid = f"ui:api.{name}"
        g.add_node(Node(fid, "ui", "api-client", f"api.{name}", _rel(root, client), _lineno(text, m.start())))
        g.add_edge(fid, route_id, "calls", _rel(root, client), _lineno(text, m.start()))
    for page in sorted((root / "web/src/pages").glob("*.tsx")):
        ptext = page.read_text()
        pid = f"ui:{page.stem}"
        g.add_node(Node(pid, "ui", "component", page.stem, _rel(root, page), 1))
        for m in re.finditer(r"\bapi\.(\w+)\(", ptext):
            g.add_edge(pid, f"ui:api.{m.group(1)}", "calls", _rel(root, page), _lineno(ptext, m.start()))
        for m in re.finditer(r"\b(COST_CENTER_CODE_PATTERN|COST_CENTER_CODE_WIDTH|padCostCenterCode|normalizeTaxId)\b", ptext):
            g.add_edge(pid, f"ui:lib.{m.group(1)}", "uses", _rel(root, page), _lineno(ptext, m.start()))
    fmt = root / "web/src/lib/format.ts"
    ftext = fmt.read_text()
    for m in re.finditer(r"export (?:const|function) (\w+)[^=\n(]*(?:= (.+))?", ftext):
        attrs = {}
        if m.group(2) and m.group(2).strip().isdigit():
            attrs["width"] = int(m.group(2))
        if m.group(2) and m.group(2).startswith("/"):
            attrs["regex"] = m.group(2).rstrip()
        if not m.group(2):
            body_end = ftext.find("\n}", m.end())
            rm = re.search(r"\.replace\(/(.+?)/[a-z]*,", ftext[m.end() : body_end])
            if rm:
                attrs["regex"] = rm.group(1)
        g.add_node(
            Node(
                f"ui:lib.{m.group(1)}",
                "ui",
                "constant" if m.group(2) else "function",
                m.group(1),
                _rel(root, fmt),
                _lineno(ftext, m.start()),
                attrs,
            )
        )
    g.add_edge("ui:lib.normalizeTaxId", "api:validators.normalize_tax_id", "mirrors", _rel(root, fmt))
    g.add_edge("ui:lib.COST_CENTER_CODE_PATTERN", "api:validators.validate_cost_center_code", "mirrors", _rel(root, fmt))
    g.add_edge("ui:lib.padCostCenterCode", "ui:lib.COST_CENTER_CODE_WIDTH", "uses", _rel(root, fmt))


# ---------------------------------------------------------------------------------------------- pipelines
def extract_pipelines(root: Path, g: Graph) -> None:
    for yp in sorted((root / "pipelines/sources").glob("*.yaml")):
        data = yaml.safe_load(yp.read_text())
        sid = f"source:{data['name']}"
        g.add_node(Node(sid, "source", "source-contract", data["name"], _rel(root, yp), 1, {"system": data["system"]}))
        g.add_edge(sid, f"warehouse:{data['target_table'].upper()}", "lands-in", _rel(root, yp))
        for e in data.get("expectations", []):
            if e.get("type") in {"regex", "max_length"}:
                eid = f"source:{data['name']}.expect.{e['column']}"
                g.add_node(
                    Node(
                        eid,
                        "source",
                        "expectation",
                        f"{data['name']}: {e['type']} {e['column']}",
                        _rel(root, yp),
                        1,
                        {"regex": e.get("pattern"), "width": e.get("value")},
                    )
                )
                g.add_edge(sid, eid, "has-expectation")
    for jp in sorted((root / "pipelines/jobs").glob("*.py")):
        if jp.name == "__init__.py":
            continue
        text = jp.read_text()
        jid = f"pipeline:{jp.stem}"
        g.add_node(Node(jid, "pipeline", "spark-job", jp.stem, _rel(root, jp), 1))
        for m in re.finditer(r'load_source\("(\w+)"\)', text):
            g.add_edge(jid, f"source:{m.group(1)}", "reads-contract", _rel(root, jp), _lineno(text, m.start()))
        for m in SNOWFLAKE_OBJ.finditer(text):
            obj = f"FDP_MDM.{m.group(1).upper()}.{m.group(2).upper()}"
            ctx = text[max(0, m.start() - 40) : m.start()].upper()
            kind = "writes" if any(k in ctx for k in ("INSERT", "MERGE INTO", "LOAD_DATAFRAME", "DELETE", "OVERWRITE")) else "reads"
            g.add_edge(jid, f"warehouse:{obj}", kind, _rel(root, jp), _lineno(text, m.start()))
        for m in re.finditer(r"^(CC_WIDTH|COST_CENTER_CODE_WIDTH)\s*=\s*(.+)$", text, re.MULTILINE):
            cid = f"pipeline:{jp.stem}.{m.group(1)}"
            width = re.search(r'"(\d+)"', m.group(2))
            g.add_node(
                Node(
                    cid,
                    "pipeline",
                    "constant",
                    f"{jp.stem}.{m.group(1)}",
                    _rel(root, jp),
                    _lineno(text, m.start()),
                    {
                        "width": int(width.group(1)) if width else None,
                        "concept": "cost_center_code",
                        "env_var": "COST_CENTER_CODE_WIDTH" if "environ" in m.group(2) else None,
                    },
                )
            )
            g.add_edge(jid, cid, "uses")
            if "environ" in m.group(2):
                g.add_edge(cid, "config:COST_CENTER_CODE_WIDTH", "reads-env")
        for m in re.finditer(r"F\.lpad\(([^,]+),\s*(\d+)\s*,", text):
            col = re.sub(r"[^a-z_]", "", m.group(1).lower().replace("f.trim", ""))
            g.add_node(
                Node(
                    f"pipeline:{jp.stem}.lpad@{_lineno(text, m.start())}",
                    "pipeline",
                    "literal",
                    f"{jp.stem}: lpad({col}, {m.group(2)})",
                    _rel(root, jp),
                    _lineno(text, m.start()),
                    {"width": int(m.group(2)), "concept": col},
                )
            )
            g.add_edge(jid, f"pipeline:{jp.stem}.lpad@{_lineno(text, m.start())}", "uses")
        ptree = ast.parse(text)
        for fn in [n for n in ptree.body if isinstance(n, ast.FunctionDef)]:
            if "tax_id" in fn.name:
                fid = f"pipeline:{jp.stem}.{fn.name}"
                g.add_node(
                    Node(
                        fid,
                        "pipeline",
                        "udf",
                        fn.name,
                        _rel(root, jp),
                        fn.lineno,
                        {"regex": _first_regex(ast.get_source_segment(text, fn) or "") or "replace('-', '')"},
                    )
                )
                g.add_edge(jid, fid, "uses")
                g.add_edge(fid, "api:validators.normalize_tax_id", "mirrors", _rel(root, jp), fn.lineno)
    wp = root / "pipelines/warehouse/duckdb_warehouse.py"
    g.add_node(
        Node(
            "pipeline:warehouse.DuckDBWarehouse",
            "pipeline",
            "adapter",
            "DuckDBWarehouse",
            _rel(root, wp),
            1,
            {"dialect": "snowflake->duckdb"},
        )
    )
    g.add_node(
        Node(
            "pipeline:warehouse.SnowflakeWarehouse",
            "pipeline",
            "adapter",
            "SnowflakeWarehouse",
            "pipelines/warehouse/snowflake_warehouse.py",
            1,
        )
    )


# ---------------------------------------------------------------------------------------------- snowflake
def extract_snowflake(root: Path, g: Graph) -> None:
    for sp in sorted((root / "snowflake/sql").glob("*.sql")):
        text = sp.read_text()
        for m in re.finditer(
            r"CREATE\s+(?:OR\s+REPLACE\s+)?(TABLE|VIEW|FUNCTION|PROCEDURE|TASK|STAGE)(?:\s+IF\s+NOT\s+EXISTS)?\s+(FDP_MDM\.\w+\.\w+)(\([^)]*\))?",
            text,
            re.IGNORECASE,
        ):
            kind, name, args = m.group(1).lower(), m.group(2).upper(), (m.group(3) or "")
            nid = f"warehouse:{name}"
            end = text.find(";", m.end())
            # statements with $$ bodies end at the closing $$;
            if "$$" in text[m.end() : end if end > 0 else len(text)] or kind in {"procedure", "function"}:
                dd = text.find("$$", m.end())
                dd2 = text.find("$$", dd + 2) if dd > 0 else -1
                end = text.find(";", dd2) if dd2 > 0 else end
            body = text[m.end() : end if end > 0 else len(text)]
            g.add_node(
                Node(
                    nid,
                    "warehouse",
                    kind,
                    name,
                    _rel(root, sp),
                    _lineno(text, m.start()),
                    {"regex": _sql_regex(body), "args": args} if kind in {"function", "procedure"} else {},
                )
            )
            if kind == "table":
                for cm in VARCHAR_COL.finditer(body):
                    cid = f"warehouse:{name}.{cm.group(1).upper()}"
                    g.add_node(
                        Node(
                            cid,
                            "warehouse",
                            "column",
                            f"{name}.{cm.group(1).upper()}",
                            _rel(root, sp),
                            _lineno(text, m.end() + cm.start()),
                            {"width": int(cm.group(2))},
                        )
                    )
                    g.add_edge(nid, cid, "has-column")
            for rm in SNOWFLAKE_OBJ.finditer(body):
                ref = f"FDP_MDM.{rm.group(1).upper()}.{rm.group(2).upper()}"
                if ref != name:
                    ctx = body[max(0, rm.start() - 30) : rm.start()].upper()
                    ek = "writes" if any(k in ctx for k in ("INSERT INTO", "MERGE INTO", "UPDATE", "DELETE FROM", "TRUNCATE")) else "reads"
                    g.add_edge(nid, f"warehouse:{ref}", ek, _rel(root, sp), _lineno(text, m.start()))
    g.add_edge("warehouse:FDP_MDM.UTIL.FN_NORMALIZE_TAX_ID", "api:validators.normalize_tax_id", "mirrors", "snowflake/sql/040_udfs.sql", 3)


def _sql_regex(body: str) -> str | None:
    m = re.search(r"REGEXP_(?:REPLACE|LIKE)\([^,]+,\s*'([^']+)'", body)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------------------------- terraform
def extract_terraform(root: Path, g: Graph) -> None:
    tf_dir = root / "infra/terraform"
    for tp in sorted(tf_dir.glob("*.tf")):
        text = tp.read_text()
        for m in re.finditer(r'^resource\s+"(\w+)"\s+"(\w+)"\s*\{', text, re.MULTILINE):
            addr = f"{m.group(1)}.{m.group(2)}"
            nid = f"infra:{addr}"
            start, depth, i = m.end(), 1, m.end()
            while i < len(text) and depth:
                depth += {"{": 1, "}": -1}.get(text[i], 0)
                i += 1
            body = text[start:i]
            g.add_node(Node(nid, "infra", m.group(1), addr, _rel(root, tp), _lineno(text, m.start())))
            for sm in re.finditer(r"script_location\s*=\s*\"[^\"]*/jobs/([\w/]+)\.py\"", body):
                g.add_edge(
                    nid,
                    f"{'legacy' if 'legacy' in sm.group(1) else 'pipeline'}:{Path(sm.group(1)).stem}",
                    "deploys",
                    _rel(root, tp),
                    _lineno(text, m.start()),
                )
            for vm in re.finditer(r"var\.(\w+)", body):
                g.add_edge(nid, f"infra:var.{vm.group(1)}", "configures", _rel(root, tp), _lineno(text, m.start()))
            for rm in re.finditer(r"\b(aws_\w+)\.(\w+)\.(?:arn|id|name|bucket|url|address|repository_url|endpoint)", body):
                g.add_edge(nid, f"infra:{rm.group(1)}.{rm.group(2)}", "depends-on", _rel(root, tp), _lineno(text, m.start()))
            for em in re.finditer(r'"?(COST_CENTER_CODE_WIDTH|MDM_\w+|SNOWFLAKE_\w+)"?\s*=', body):
                g.add_node(Node(f"config:{em.group(1)}", "config", "env-var", em.group(1), _rel(root, tp), _lineno(text, m.start())))
                g.add_edge(nid, f"config:{em.group(1)}", "sets-env", _rel(root, tp), _lineno(text, m.start()))
            for fm in re.finditer(r'filename\s*=\s*"\$\{path\.module\}/([\w/]+\.py)"', body):
                g.add_edge(nid, f"infra:lambda/{Path(fm.group(1)).stem}", "deploys", _rel(root, tp))
            for sfm in re.finditer(r'file\("\$\{path\.module\}/(state_machines/[\w]+\.asl\.json)"\)', body):
                g.add_edge(nid, f"infra:{sfm.group(1)}", "defines", _rel(root, tp))
        for m in re.finditer(r'^variable\s+"(\w+)"\s*\{(.*?)^\}', text, re.MULTILINE | re.DOTALL):
            default = re.search(r"default\s*=\s*(\S+)", m.group(2))
            attrs = {"default": default.group(1).strip('"') if default else None}
            if m.group(1).endswith("width") and default:
                attrs["width"] = int(default.group(1))
            g.add_node(
                Node(f"infra:var.{m.group(1)}", "infra", "variable", f"var.{m.group(1)}", _rel(root, tp), _lineno(text, m.start()), attrs)
            )
    for ev in sorted((tf_dir / "envs").glob("*.tfvars")):
        env = ev.stem
        text = ev.read_text()
        for m in re.finditer(r"^(\w+)\s*=\s*(.+)$", text, re.MULTILINE):
            vid = f"infra:var.{m.group(1)}"
            node = g.nodes.get(vid)
            if node is None:
                node = g.add_node(Node(vid, "infra", "variable", f"var.{m.group(1)}", _rel(root, ev), _lineno(text, m.start())))
            node.attrs.setdefault("per_env", {})[env] = m.group(2).strip().strip('"')
    lam = tf_dir / "lambda/publish_notifier.py"
    text = lam.read_text()
    g.add_node(Node("infra:lambda/publish_notifier", "infra", "lambda-handler", "publish_notifier.py", _rel(root, lam), 1))
    for m in SNOWFLAKE_OBJ.finditer(text):
        g.add_edge(
            "infra:lambda/publish_notifier",
            f"warehouse:FDP_MDM.{m.group(1).upper()}.{m.group(2).upper()}",
            "calls",
            _rel(root, lam),
            _lineno(text, m.start()),
        )
    g.add_edge("infra:aws_s3_bucket.publish", "infra:lambda/publish_notifier", "triggers", "infra/terraform/lambda.tf")
    sf = tf_dir / "state_machines/nightly_mdm.asl.json"
    asl = json.loads(sf.read_text())
    sid = "infra:state_machines/nightly_mdm.asl.json"
    g.add_node(Node(sid, "infra", "step-function", "nightly_mdm", _rel(root, sf), 1))
    for state in asl.get("States", {}).values():
        job = (state.get("Parameters") or {}).get("JobName", "")
        jm = re.search(r"aws_glue_job\.(\w+)", job)
        if jm:
            g.add_edge(sid, f"infra:aws_glue_job.{jm.group(1)}", "runs", _rel(root, sf))


# ---------------------------------------------------------------------------------------------- legacy
def extract_legacy(root: Path, g: Graph) -> None:
    for lp in sorted((root / "legacy").rglob("*.py")):
        text = lp.read_text()
        lid = f"legacy:{lp.stem}"
        g.add_node(Node(lid, "legacy", "batch-script", lp.stem, _rel(root, lp), 1))
        for m in SNOWFLAKE_OBJ.finditer(text):
            ctx = text[max(0, m.start() - 30) : m.start()].upper()
            kind = "writes" if any(k in ctx for k in ("INSERT INTO", "DELETE FROM", "UPDATE")) else "reads"
            g.add_edge(lid, f"warehouse:FDP_MDM.{m.group(1).upper()}.{m.group(2).upper()}", kind, _rel(root, lp), _lineno(text, m.start()))
        for m in re.finditer(r"^(CC_WIDTH)\s*=\s*(\d+)", text, re.MULTILINE):
            cid = f"legacy:{lp.stem}.{m.group(1)}"
            g.add_node(
                Node(
                    cid,
                    "legacy",
                    "constant",
                    f"{lp.stem}.{m.group(1)}",
                    _rel(root, lp),
                    _lineno(text, m.start()),
                    {"width": int(m.group(2)), "concept": "cost_center_code"},
                )
            )
            g.add_edge(lid, cid, "uses")
        ltree = ast.parse(text)
        for fn in [n for n in ltree.body if isinstance(n, ast.FunctionDef)]:
            if "tax_id" in fn.name:
                fid = f"legacy:{lp.stem}.{fn.name}"
                g.add_node(
                    Node(
                        fid,
                        "legacy",
                        "function",
                        fn.name,
                        _rel(root, lp),
                        fn.lineno,
                        {"regex": _first_regex(ast.get_source_segment(text, fn) or "")},
                    )
                )
                g.add_edge(lid, fid, "uses")
                g.add_edge(fid, "api:validators.normalize_tax_id", "mirrors", _rel(root, lp), fn.lineno)
        _inherit_constant_regex(g, ltree, text, f"legacy:{lp.stem}.", _rel(root, lp))
    for sp in sorted((root / "legacy").rglob("*.sql")):
        text = sp.read_text()
        lid = f"legacy:{sp.stem}"
        g.add_node(Node(lid, "legacy", "sql-script", sp.stem, _rel(root, sp), 1, {"regex": _sql_regex(text)}))
        for m in SNOWFLAKE_OBJ.finditer(text):
            g.add_edge(
                lid, f"warehouse:FDP_MDM.{m.group(1).upper()}.{m.group(2).upper()}", "reads", _rel(root, sp), _lineno(text, m.start())
            )
        if "TAX_ID" in text.upper():
            g.add_edge(lid, "warehouse:FDP_MDM.UTIL.FN_NORMALIZE_TAX_ID", "mirrors", _rel(root, sp))


# ---------------------------------------------------------------------------------------------- tests
def extract_tests(root: Path, g: Graph) -> None:
    for tp in sorted(root.glob("*/tests/test_*.py")) + sorted(root.glob("*/*/tests/test_*.py")):
        text = tp.read_text()
        tid = f"test:{tp.stem}"
        g.add_node(Node(tid, "test", "pytest", tp.stem, _rel(root, tp), 1))
        for m in re.finditer(r"\b(normalize_tax_id|validate_cost_center_code)\b", text):
            g.add_edge(tid, f"api:validators.{m.group(1)}", "covers", _rel(root, tp), _lineno(text, m.start()))
        for m in re.finditer(r"\b(ingest_\w+|match_merge_\w+)\.run\(", text):
            g.add_edge(tid, f"pipeline:{m.group(1)}", "covers", _rel(root, tp), _lineno(text, m.start()))
        routes = _route_index(g)
        for m in re.finditer(r"client\.(get|post|put)\(\s*f?\"(/api/[^\"?]+)", text):
            route = re.sub(r"/(V\d+|US01|\d{6}|\{[^}]+\})(?=/|$)", "/{}", m.group(2))
            key = f"{m.group(1).upper()} {route}"
            g.add_edge(tid, routes.get(key, f"api:{key}"), "covers", _rel(root, tp), _lineno(text, m.start()))


EXTRACTORS = [extract_api, extract_ui, extract_pipelines, extract_snowflake, extract_terraform, extract_legacy, extract_tests]


def build_graph(root: Path) -> Graph:
    g = Graph()
    for ex in EXTRACTORS:
        ex(root, g)
    g.finalize()
    return g
