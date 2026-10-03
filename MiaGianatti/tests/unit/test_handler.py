import importlib
import os
import json
import pathlib
import sys
import types
import pytest
import boto3
import responses
from unittest.mock import patch, MagicMock
from moto import mock_aws

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lambda"))
sys.path.insert(0, str(ROOT))

HANDLER_PATH = ROOT / "lambda" / "handler.py"
TABLE_NAME = "test-table"
TEST_URL = "https://www.google.com"

class FakeTable:
    def __init__(self):
        self.items = []
 
    def put_item(self, Item):
        self.items.append(Item)
 
 
class FakeDynamoDB:
    def __init__(self):
        self.tables = {}
 
    def Table(self, name):
        return self.tables.setdefault(name, FakeTable())

TABLE_NAME = "ALARM_NOTIFICATIONS_TABLE"
@pytest.fixture
def ALARM_NOTIFICATIONS_TABLE(aws_credentials, monkeypatch):
    monkeypatch.setenv("ALARM_NOTFICATIONS_TABLE", TABLE_NAME)
    with mock_aws():
        dynamo = boto3.client("dynamodb", region_name="us-east-1")
        dynamo.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield TABLE_NAME


def sns_event(alarm="web-alarm", new="ALARM", old="OK", event_source="aws:sns", **extra):
    message = {"AlarmName": alarm, "NewStateValue": new, "OldStateValue": old, **extra}
    return {"Records": [{"EventSource": event_source, "Sns": {"Message": json.dumps(message)}}]}

@pytest.fixture
def handler(monkeypatch):
    monkeypatch.setenv("ALARM_NOTIFICATIONS_TABLE", TABLE_NAME)
 
    constants = types.ModuleType("constants")
    constants.URL = TEST_URL
    constants.NAMESPACE = "TestNamespace"
    constants.METRIC_AVAILABILITY = "AVAILABILITY"
    constants.METRIC_LATENCY = "LATENCY"
    constants.METRIC_RESPONSE_SIZE = "RESPONSE_SIZE"
 
    cw = types.ModuleType("CWPutData")
    cw.calls = []
    cw.putDataFunction = lambda ns, metric, url, value: cw.calls.append((ns, metric, url, value))
 
    monkeypatch.setitem(sys.modules, "constants", constants)
    monkeypatch.setitem(sys.modules, "CWPutData", cw)
 
    import boto3
 
    fake_db = FakeDynamoDB()
    monkeypatch.setattr(
        boto3, "resource", lambda service, *a, **k: fake_db if service == "dynamodb" else object()
    )
 
    spec = importlib.util.spec_from_file_location("handler_under_test", HANDLER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

@pytest.fixture
def aws_credentials():
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

@pytest.fixture
def cloudwatch_client(aws_credentials):
    with mock_aws():
        yield boto3.client("cloudwatch", region_name="us-east-1")

@responses.activate
def test_health_check_publishes_metrics(monkeypatch, cloudwatch_client):
    test_url = "https://www.google.com"
    monkeypatch.setattr("handler.constants.URL", test_url)

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = b"OK"

    with patch("handler.urllib.request.urlopen", return_value = mock_response):
        result = handler.lambda_handler ({}, {})

    assert result["statusCode"] == 200

    metrics = cloudwatch_client.list_metrics(Namespace=constants.NAMESPACE)
    metric_names = {m["MetricName"] for m in metrics["Metrics"]}

    assert constants.METRIC_AVAILABILITY in metric_names
    assert constants.METRIC_LATENCY in metric_names
    assert constants.METRIC_RESPONSE_SIZE in metric_names


def test_sns_alarm_is_written_with_all_fields(handler):
    event = sns_event(
        alarm="LATENCY Alarm", new="ALARM", old="OK",
        NewStateReason="Threshold crossed", Region="Asia Pacific (Sydney)", AWSAccountId="123456789012",
    )
 
    handler.log_alarm(event["Records"][0]["Sns"])
 
    (item,) = handler.table.items
    assert item["pk"] == "LATENCY Alarm"
    assert item["new_state"] == "ALARM"
    assert item["old_state"] == "OK"
    assert item["reason"] == "Threshold crossed"
    assert item["region"] == "Asia Pacific (Sydney)"
    assert item["account_id"] == "123456789012"