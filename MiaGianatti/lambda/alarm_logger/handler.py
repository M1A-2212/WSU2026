import json
import os
from datetime import datetime, timezone

import boto3

table = boto3.resource("dynamodb").Table(os.environ["ALARM_NOTIFICATIONS_TABLE"])


def lambda_handler(event, context):
    for record in event.get("Records", []):
        if record.get("EventSource") == "aws:sns":
            log_alarm(record["Sns"])
    return {"statusCode": 200}


def log_alarm(sns_record):
    message = json.loads(sns_record["Message"])
    item = {
        "pk": message["AlarmName"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "new_state": message["NewStateValue"],
        "old_state": message["OldStateValue"],
        "reason": message.get("NewStateReason", ""),
        "region": message.get("Region", ""),
        "account_id": message.get("AWSAccountId", ""),
    }
    table.put_item(Item=item)
    print(f"Logged alarm: {item['pk']} -> {item['new_state']}")