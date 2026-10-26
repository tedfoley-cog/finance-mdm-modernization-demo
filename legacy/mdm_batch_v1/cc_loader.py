# -*- coding: utf-8 -*-
"""Fixed-width cost center loader (v1). Reads EBS FBDI-style extracts and loads DIM_COST_CENTER directly.

Record layout (positions are 1-based, interface spec v2 / MBA-3472 - code fields widened 6 -> 10):
    1-4     entity code
    5-14    cost center code (CC_WIDTH = 10)
    15-134  description (120)
    135-144 parent cost center code (CC_WIDTH = 10)
    145-156 manager employee id (12)
    157-157 status flag A/R
Every offset after the code is derived from CC_WIDTH so the layout follows the MDM key width.
"""
from __future__ import print_function

import sys
from datetime import datetime

from vendor_dedupe import normalise_tax_id  # noqa: F401  (imported for the shared --dedupe flag)

CC_WIDTH = 10
DESC_WIDTH = 120
MANAGER_WIDTH = 12

_CODE_START = 4
_DESC_START = _CODE_START + CC_WIDTH
_PARENT_START = _DESC_START + DESC_WIDTH
_MANAGER_START = _PARENT_START + CC_WIDTH
_STATUS_POS = _MANAGER_START + MANAGER_WIDTH


def parse_line(line):
    return {
        "entity_code": line[0:4].strip(),
        "cost_center_code": line[_CODE_START:_DESC_START].strip(),
        "description": line[_DESC_START:_PARENT_START].strip(),
        "parent_cost_center_code": line[_PARENT_START:_MANAGER_START].strip() or None,
        "manager_employee_id": line[_MANAGER_START:_STATUS_POS].strip() or None,
        "status": "ACTIVE" if line[_STATUS_POS:_STATUS_POS + 1] == "A" else "RETIRED",
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
