import json
import os
import time
import urllib.error
import urllib.request

import boto3
import pytest
from boto3.dynamodb.conditions import Key

from tests.helpers import sns_alarm_event

STACK = os.environ.get("WEB_HEALTH_STACK_NAME")
pytestmark = [
    pytest.mark.deployment,
    pytest.mark.skipif(not STACK, reason="set WEB_HEALTH_STACK_NAME to run deployment tests"),
]

CHECK_URL = "https://example.com/"
METRIC_NAMESPACE = "NAMESPACE"


@pytest.fixture(scope="module")
def cfn():
    return boto3.client("cloudformation")


@pytest.fixture(scope="module")
def resources(cfn):
    out, token = [], None
    while True:
        r = cfn.list_stack_resources(StackName=STACK, **({"NextToken": token} if token else {}))
        out += r["StackResourceSummaries"]
        token = r.get("NextToken")
        if not token:
            return out


def physical_ids(resources, rtype, logical_prefix=""):
    return [r["PhysicalResourceId"] for r in resources
            if r["ResourceType"] == rtype and r["LogicalResourceId"].startswith(logical_prefix)]


def one(resources, rtype, logical_prefix=""):
    ids = physical_ids(resources, rtype, logical_prefix)
    assert len(ids) == 1, f"expected one {rtype} starting {logical_prefix!r}, got {ids}"
    return ids[0]


@pytest.fixture(scope="module")
def api_url(cfn):
    outputs = cfn.describe_stacks(StackName=STACK)["Stacks"][0]["Outputs"]
    return next(o["OutputValue"] for o in outputs if o["OutputKey"].startswith("TargetsApiUrl")).rstrip("/")


def http(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw, status, headers = r.read(), r.status, r.headers
    except urllib.error.HTTPError as e:
        raw, status, headers = e.read(), e.code, e.headers
    return status, (json.loads(raw) if raw else None), headers


def test_crawler_runs_and_publishes_metrics_for_a_new_target(resources, api_url):
    fn = one(resources, "AWS::Lambda::Function", "webHealthFunction")
    _, target, _ = http("POST", f"{api_url}/targets", {"url": CHECK_URL})
    try:
        result = boto3.client("lambda").invoke(FunctionName=fn, Qualifier="live")
        assert result["StatusCode"] == 200 and "FunctionError" not in result

        cw = boto3.client("cloudwatch")
        deadline, value = time.time() + 180, None
        while time.time() < deadline and value is None:   # CloudWatch ingestion is eventually consistent
            now = time.time()
            pts = cw.get_metric_statistics(
                Namespace=METRIC_NAMESPACE, MetricName="AVAILABILITY",
                Dimensions=[{"Name": "URL", "Value": CHECK_URL}],
                StartTime=now - 900, EndTime=now + 60, Period=60, Statistics=["Maximum"])["Datapoints"]
            value = max(p["Maximum"] for p in pts) if pts else None
            if value is None:
                time.sleep(10)
        assert value == 1, "AVAILABILITY datapoint did not appear (or site was down)"
    finally:
        http("DELETE", f"{api_url}/targets/{target['id']}")


def test_same_notification_reaches_logger_and_rollback(system):
    import io, json, sys, types, zipfile
    from tests.helpers import REPO_ROOT
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from webHealthStack import ROLLBACK_CODE
    finally:
        sys.path.remove(str(REPO_ROOT))

    trust = json.dumps({"Version": "2012-10-17", "Statement": [{
        "Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}]})
    role = boto3.client("iam").create_role(RoleName="r", AssumeRolePolicyDocument=trust)["Role"]["Arn"]
    lam = boto3.client("lambda")

    def code(n):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("handler.py", f"x={n}")
        return buf.getvalue()

    lam.create_function(FunctionName="crawler-fn", Runtime="python3.12", Role=role,
                        Handler="handler.lambda_handler", Code={"ZipFile": code(0)})
    for n in (1, 2):
        lam.update_function_code(FunctionName="crawler-fn", ZipFile=code(n))
        lam.publish_version(FunctionName="crawler-fn")
    lam.create_alias(FunctionName="crawler-fn", Name="live", FunctionVersion="2")

    rollback = types.ModuleType("rb")
    exec(ROLLBACK_CODE, rollback.__dict__)

    event = sns_alarm_event("WebHealthStack-CrawlerErrors", "ALARM", "OK")
    system.alarm_logger.lambda_handler(event, None)
    rollback_result = rollback.lambda_handler(event, None)

    assert rollback_result["to"] == "1"
    assert lam.get_alias(FunctionName="crawler-fn", Name="live")["FunctionVersion"] == "1"
    assert system.alarms_table.scan()["Count"] == 1



def test_api_crud_lifecycle_over_http(api_url):
    status, created, headers = http("POST", f"{api_url}/targets", {"url": "https://deploy-test.example.com/"})
    assert status == 201
    tid = created["id"]
    try:
        assert headers.get("Access-Control-Allow-Origin") == "*"
        assert http("GET", f"{api_url}/targets/{tid}")[1]["url"] == "https://deploy-test.example.com/"
        assert any(t["id"] == tid for t in http("GET", f"{api_url}/targets")[1])

        status, updated, _ = http("PUT", f"{api_url}/targets/{tid}", {"enabled": False})
        assert status == 200 and updated["enabled"] is False
    finally:
        assert http("DELETE", f"{api_url}/targets/{tid}")[0] == 204
    assert http("GET", f"{api_url}/targets/{tid}")[0] == 404