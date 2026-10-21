# -*- coding: utf-8 -*-
"""v1 vendor de-duplication helpers. Superseded by pipelines/jobs/match_merge_vendors.py but still imported
by cc_loader.py and shipped with the legacy Glue job."""
import re

_NON_ALNUM = re.compile(r"[^A-Za-z0-9]")


def normalise_tax_id(raw):
    """Strip every non-alphanumeric character and upper-case."""
    if raw is None:
        return None
    v = _NON_ALNUM.sub("", raw).upper()
    return v or None


def match_key(vendor):
    tax = normalise_tax_id(vendor.get("tax_id"))
    if tax:
        return "TAX:" + tax
    return "NAME:" + re.sub(r"\W+", "", vendor.get("legal_name", "")).upper()[:40]


def group_duplicates(vendors):
    groups = {}
    for v in vendors:
        groups.setdefault(match_key(v), []).append(v)
    return [g for g in groups.values() if len(g) > 1]
