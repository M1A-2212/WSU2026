import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3

REPO_ROOT = Path(__file__).resolve().parent.parent
LAMBDA_DIRS = {
    "crawler": REPO_ROOT / "lambda" / "crawler",
    "alarm_logger": REPO_ROOT / "lambda" / "alarm_logger",
    "crud": REPO_ROOT / "lambda" / "crud",
}
_SIBLINGS = ("handler", "CWPutData", "constants")


def load_lambda(name):
    folder = LAMBDA_DIRS[name]
    saved = {m: sys.modules.pop(m, None) for m in _SIBLINGS}
    sys.path.insert(0, str(folder))
    try:
        spec = importlib.util.spec_from_file_location(f"{name}_handler", folder / "handler.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(folder))
        for m in _SIBLINGS:
            sys.modules.pop(m, None)
            if saved[m] is not None:
                sys.modules[m] = saved[m]


def api_event(method, target_id=None, body=None, raw_body=None):
    event = {"httpMethod": method, "pathParameters": {"id": target_id} if target_id else None}
    if raw_body is not None:
        event["body"] = raw_body
    elif body is not None:
        event["body"] = json.dumps(body)
    else:
        event["body"] = None
    return event


def sns_alarm_event(alarm_name="CrawlerErrors", new="ALARM", old="OK", **extra):
    message = {
        "AlarmName": alarm_name,
        "NewStateValue": new,
        "OldStateValue": old,
        "NewStateReason": "Threshold Crossed",
        "Region": "US East (N. Virginia)",
        "AWSAccountId": "123456789012",
    }
    message.update(extra)
    return {"Records": [{"EventSource": "aws:sns", "Sns": {"Message": json.dumps(message)}}]}


def metric_value(namespace, name, url=None, stat="Maximum"):
    cw = boto3.client("cloudwatch")
    now = datetime.now(timezone.utc)
    kwargs = dict(Namespace=namespace, MetricName=name,
                  StartTime=now - timedelta(minutes=10), EndTime=now + timedelta(minutes=10),
                  Period=60, Statistics=[stat])
    if url:
        kwargs["Dimensions"] = [{"Name": "URL", "Value": url}]
    points = cw.get_metric_statistics(**kwargs)["Datapoints"]
    return max(points, key=lambda p: p["Timestamp"])[stat] if points else None

