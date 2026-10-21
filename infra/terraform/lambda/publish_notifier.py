"""S3 ObjectCreated -> call the Snowflake load procedure for the published entity type.

Key layout produced by api/app/services/publish.py:
    golden/<entity_type>/dt=YYYY-MM-DD/<run_id>.jsonl
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.parse
import urllib.request

import boto3

log = logging.getLogger()
log.setLevel(logging.INFO)

COST_CENTER_CODE_WIDTH = int(os.environ.get("COST_CENTER_CODE_WIDTH", "6"))
KEY_RE = re.compile(r"^golden/(?P<entity>vendor|cost_center|gl_account)/dt=\d{4}-\d{2}-\d{2}/(?P<run_id>[0-9TZ]+)\.jsonl$")
PROCEDURES = {
    "cost_center": "FDP_MDM.UTIL.SP_LOAD_COST_CENTERS",
    "vendor": "FDP_MDM.UTIL.SP_LOAD_VENDORS",
}

_secrets = boto3.client("secretsmanager")
_s3 = boto3.client("s3")
_sns = boto3.client("sns")


def _snowflake_token() -> str:
    secret = _secrets.get_secret_value(SecretId=os.environ["SNOWFLAKE_SECRET_ARN"])
    return json.loads(secret["SecretString"])["oauth_token"]


def _call_procedure(procedure: str, run_id: str) -> dict:
    body = json.dumps({"statement": f"CALL {procedure}('{run_id}')", "timeout": 60,
                       "warehouse": "FDP_TRANSFORM_WH"}).encode()
    req = urllib.request.Request(
        f"{os.environ['SNOWFLAKE_ACCOUNT_URL']}/api/v2/statements",
        data=body,
        headers={"Authorization": f"Bearer {_snowflake_token()}", "Content-Type": "application/json",
                 "X-Snowflake-Authorization-Token-Type": "OAUTH"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
        return json.load(resp)


def _validate_cost_center_file(bucket: str, key: str) -> list[str]:
    """Defensive check: refuse to load a cost-center file whose codes are not the configured width."""
    body = _s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode()
    bad = []
    for line in body.splitlines():
        if not line.strip():
            continue
        code = json.loads(line).get("cost_center_code", "")
        if len(code) != COST_CENTER_CODE_WIDTH or not code.isdigit():
            bad.append(code)
    return bad


def handler(event: dict, _context) -> dict:
    results = []
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
        match = KEY_RE.match(key)
        if not match:
            log.warning("ignoring unexpected key %s", key)
            continue
        entity, run_id = match["entity"], match["run_id"]
        if entity == "cost_center":
            bad = _validate_cost_center_file(bucket, key)
            if bad:
                _sns.publish(TopicArn=os.environ["ALERT_TOPIC_ARN"], Subject="MDM publish rejected",
                             Message=f"{key}: {len(bad)} cost center codes not {COST_CENTER_CODE_WIDTH} digits: {bad[:10]}")
                results.append({"key": key, "status": "REJECTED"})
                continue
        if entity in PROCEDURES:
            resp = _call_procedure(PROCEDURES[entity], run_id)
            results.append({"key": key, "status": "LOADED", "statementHandle": resp.get("statementHandle")})
        else:
            results.append({"key": key, "status": "NO_PROCEDURE"})
    return {"results": results}
