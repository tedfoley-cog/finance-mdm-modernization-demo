# -*- coding: utf-8 -*-
"""Fixed-width cost center loader (v1). Reads EBS FBDI-style extracts and loads DIM_COST_CENTER directly.

Record layout (positions are 1-based, as in the 2019 interface spec):
    1-4   entity code
    5-10  cost center code (6)
    11-130 description
    131-136 parent cost center code (6)
    137-148 manager employee id
    149-149 status flag A/R
"""
from __future__ import print_function

import sys
from datetime import datetime

from vendor_dedupe import normalise_tax_id  # noqa: F401  (imported for the shared --dedupe flag)

CC_WIDTH = 6


def parse_line(line):
    return {
        "entity_code": line[0:4].strip(),
        "cost_center_code": line[4:4 + CC_WIDTH].strip(),
        "description": line[10:130].strip(),
        "parent_cost_center_code": line[130:130 + CC_WIDTH].strip() or None,
        "manager_employee_id": line[136:148].strip() or None,
        "status": "ACTIVE" if line[148:149] == "A" else "RETIRED",
    }


def division_code(cost_center_code):
    return cost_center_code[:3]


def load(path, cursor):
    rows = []
    with open(path) as fh:
        for raw in fh:
            if not raw.strip():
                continue
            rec = parse_line(raw.rstrip("\n"))
            rec["division_code"] = division_code(rec["cost_center_code"])
            rows.append(rec)
    cursor.execute("DELETE FROM FDP_MDM.CURATED.DIM_COST_CENTER WHERE SOURCE_SYSTEM = 'EBS_FW'")
    cursor.executemany(
        "INSERT INTO FDP_MDM.CURATED.DIM_COST_CENTER (ENTITY_CODE, COST_CENTER_CODE, DESCRIPTION, "
        "PARENT_COST_CENTER_CODE, DIVISION_CODE, MANAGER_EMPLOYEE_ID, STATUS, SOURCE_SYSTEM, UPDATED_AT) "
        "VALUES (%(entity_code)s, %(cost_center_code)s, %(description)s, %(parent_cost_center_code)s, "
        "%(division_code)s, %(manager_employee_id)s, %(status)s, 'EBS_FW', %(now)s)",
        [dict(r, now=datetime.utcnow()) for r in rows],
    )
    return len(rows)


if __name__ == "__main__":
    import snowflake.connector

    conn = snowflake.connector.connect(connection_name="fdp_loader")
    n = load(sys.argv[1], conn.cursor())
    print("loaded %d cost centers" % n)
