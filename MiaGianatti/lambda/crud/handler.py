import json
import os
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse
import boto3

table = boto3.resource("dynamodb").Table(os.environ["TARGETS_TABLE"])
ConditionFailed = table.meta.client.exceptions.ConditionalCheckFailedException


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


def list_targets():
    items, kwargs = [], {}
    while True:
        r = table.scan(**kwargs)
        items += r["Items"]
        if "LastEvaluatedKey" not in r:
            break
        kwargs["ExclusiveStartKey"] = r["LastEvaluatedKey"]
    return resp(200, items)


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