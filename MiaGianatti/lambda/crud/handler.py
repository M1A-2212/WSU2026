import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
import boto3

table = boto3.resource("dynamodb").Table(os.environ["TARGETS_TABLE"])
ConditionFailed = table.meta.client.exceptions.ConditionalCheckFailedException
cw = boto3.client("cloudwatch")

METRICS_NAMESPACE = os.environ.get("METRICS_NAMESPACE", "NAMESPACE")

METRICS = {
    "availability": (os.environ.get("METRIC_AVAILABILITY", "AVAILABILITY"), "Minimum"),
    "latency": (os.environ.get("METRIC_LATENCY", "LATENCY"), "Average"),
    "response_size": (os.environ.get("METRIC_RESPONSE_SIZE", "RESPONSE_SIZE"), "Average"),
}
PERIOD_SECONDS = 300
MAX_HOURS = 24
TARGETS_PER_CALL = 100


def resp(status, body=None):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
        "body": json.dumps(body) if body is not None else "",
    }


def valid_url(u):
    p = urlparse(u or "")
    return p.scheme in ("http", "https") and bool(p.netloc)


def now():
    return datetime.now(timezone.utc).isoformat()

def lambda_handler(event, context):
    method = event["httpMethod"]
    target_id = (event.get("pathParameters") or {}).get("id")

    try:
        body = json.loads(event["body"]) if event.get("body") else {}
    except json.JSONDecodeError:
        return resp(400, {"error": "Body must be valid JSON"})

    resource = event.get("resource", "")
    qs = event.get("queryStringParameters") or {}
    if method == "GET" and resource == "/metrics":
        return all_metrics(qs)
    if method == "GET" and target_id and resource.endswith("/metrics"):
        return target_metrics(target_id, qs)

    if method == "GET" and not target_id:
        return list_targets()
    if method == "POST" and not target_id:
        return create_target(body)
    if method == "GET":
        return get_target(target_id)
    if method == "PUT":
        return update_target(target_id, body)
    if method == "DELETE":
        return delete_target(target_id)
    return resp(405, {"error": "Method not allowed"})


def scan_targets():
    items, kwargs = [], {}
    while True:
        r = table.scan(**kwargs)
        items += r["Items"]
        if "LastEvaluatedKey" not in r:
            return items
        kwargs["ExclusiveStartKey"] = r["LastEvaluatedKey"]


def list_targets():
    return resp(200, scan_targets())


def create_target(body):
    if not valid_url(body.get("url")):
        return resp(400, {"error": "'url' must be a valid http(s) URL"})
    item = {
        "id": str(uuid.uuid4()),
        "url": body["url"],
        "enabled": bool(body.get("enabled", True)),
        "created_at": now(),
        "updated_at": now(),
    }
    table.put_item(Item=item)
    return resp(201, item)


def get_target(target_id):
    item = table.get_item(Key={"id": target_id}).get("Item")
    return resp(200, item) if item else resp(404, {"error": "Not found"})


def update_target(target_id, body):
    sets, names, values = ["updated_at = :u"], {}, {":u": now()}
    if "url" in body:
        if not valid_url(body["url"]):
            return resp(400, {"error": "'url' must be a valid http(s) URL"})
        sets.append("#url = :url")
        names["#url"] = "url"
        values[":url"] = body["url"]
    if "enabled" in body:
        sets.append("enabled = :e")
        values[":e"] = bool(body["enabled"])
    try:
        r = table.update_item(
            Key={"id": target_id},
            UpdateExpression="SET " + ", ".join(sets),
            ExpressionAttributeValues=values,
            **({"ExpressionAttributeNames": names} if names else {}),
            ConditionExpression="attribute_exists(id)",
            ReturnValues="ALL_NEW",
        )
        return resp(200, r["Attributes"])
    except ConditionFailed:
        return resp(404, {"error": "Not found"})


def delete_target(target_id):
    try:
        table.delete_item(Key={"id": target_id}, ConditionExpression="attribute_exists(id)")
        return resp(204)
    except ConditionFailed:
        return resp(404, {"error": "Not found"})


# ---------- Crawler metrics ----------

def parse_hours(qs):
    try:
        hours = int(qs.get("hours", 1))
    except (TypeError, ValueError):
        hours = 1
    return min(max(hours, 1), MAX_HOURS)


def fetch_metrics(targets, hours):
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)
    out = {t["id"]: {name: [] for name in METRICS} for t in targets}

    for i in range(0, len(targets), TARGETS_PER_CALL):
        chunk = targets[i:i + TARGETS_PER_CALL]
        queries, index = [], {}
        for ti, t in enumerate(chunk):
            for mi, (name, (metric, stat)) in enumerate(METRICS.items()):
                qid = f"q{ti}_{mi}"
                index[qid] = (t["id"], name)
                queries.append({
                    "Id": qid,
                    "MetricStat": {
                        "Metric": {
                            "Namespace": METRICS_NAMESPACE,
                            "MetricName": metric,
                            "Dimensions": [{"Name": "URL", "Value": t["url"]}],
                        },
                        "Period": PERIOD_SECONDS,
                        "Stat": stat,
                    },
                    "ReturnData": True,
                })

        kwargs = {
            "MetricDataQueries": queries,
            "StartTime": start,
            "EndTime": end,
            "ScanBy": "TimestampAscending",
        }
        while True:
            r = cw.get_metric_data(**kwargs)
            for res in r["MetricDataResults"]:
                tid, name = index[res["Id"]]
                out[tid][name] += [
                    {"timestamp": ts.isoformat(), "value": v}
                    for ts, v in zip(res["Timestamps"], res["Values"])
                ]
            if not r.get("NextToken"):
                break
            kwargs["NextToken"] = r["NextToken"]
    return out


def summarise(target, series, include_points):
    latest = {name: (pts[-1]["value"] if pts else None) for name, pts in series.items()}
    avail = latest["availability"]
    status = "no_data" if avail is None else ("up" if avail >= 1 else "down")
    result = {
        "id": target["id"],
        "url": target["url"],
        "enabled": target.get("enabled", True),
        "status": status,
        "latest": latest,
    }
    if include_points:
        result["datapoints"] = series
    return result


def target_metrics(target_id, qs):
    target = table.get_item(Key={"id": target_id}).get("Item")
    if not target:
        return resp(404, {"error": "Not found"})
    hours = parse_hours(qs)
    series = fetch_metrics([target], hours)[target["id"]]
    body = summarise(target, series, include_points=True)
    body["hours"] = hours
    body["period_seconds"] = PERIOD_SECONDS
    return resp(200, body)


def all_metrics(qs):
    targets = scan_targets()
    hours = parse_hours(qs)
    series = fetch_metrics(targets, hours)
    return resp(200, [summarise(t, series[t["id"]], include_points=False) for t in targets])