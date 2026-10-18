import json

from boto3.dynamodb.conditions import Key

from tests.helpers import sns_alarm_event


def items_for(table, alarm):
    return table.query(KeyConditionExpression=Key("pk").eq(alarm))["Items"]

def test_alarm_is_written_to_table(alarm_logger, alarms_table):
    alarm_logger.lambda_handler(sns_alarm_event("LATENCY Alarm", "ALARM", "OK"), None)
    (item,) = items_for(alarms_table, "LATENCY Alarm")
    assert item["new_state"] == "ALARM" and item["old_state"] == "OK"
    assert item["account_id"] == "123456789012"
    assert item["timestamp"]

def test_non_sns_event_writes_nothing(alarm_logger, alarms_table):
    alarm_logger.lambda_handler({"Records": [{"EventSource": "aws:sqs"}]}, None)
    assert alarms_table.scan()["Count"] == 0

def test_history_accumulates_per_alarm(alarm_logger, alarms_table):
    alarm_logger.lambda_handler(sns_alarm_event("A", "ALARM", "OK"), None)
    alarm_logger.lambda_handler(sns_alarm_event("A", "OK", "ALARM"), None)
    history = items_for(alarms_table, "A")
    assert [i["new_state"] for i in sorted(history, key=lambda i: i["timestamp"])] == ["ALARM", "OK"]
