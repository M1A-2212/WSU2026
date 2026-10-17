import importlib.util
import os
import sys
import types
 
import boto3
import pytest
from moto import mock_aws
 
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAMBDA_DIR = os.path.join(ROOT, "lambda")

CRAWLER_FILE = "handler.py"
CRUD_FILE = "api_handler.py"


@pytest.fixture(autouse=True)
def aws_env(monkeypatch):
    for key, value in {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_SECURITY_TOKEN": "testing",
        "AWS_SESSION_TOKEN": "testing",
        "AWS_DEFAULT_REGION": "us-east-1",
    }.items():
        monkeypatch.setenv(key, value)
 
 
@pytest.fixture
def aws():
    with mock_aws():
        yield
 
 
def load_module(filename, module_name):
    spec = importlib.util.spec_from_file_location(
        module_name, os.path.join(LAMBDA_DIR, filename)
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

@pytest.fixture
def fake_deps(monkeypatch):
    constants = types.ModuleType("constants")
    constants.URL = "https://example.com"
    constants.NAMESPACE = "WebCrawler"
    constants.METRIC_LATENCY = "LATENCY"
    constants.METRIC_AVAILABILITY = "AVAILABILITY"
    constants.METRIC_RESPONSE_SIZE = "RESPONSE_SIZE"
 
    cwput = types.ModuleType("CWPutData")
    cwput.calls = []
    cwput.putDataFunction = lambda *args: cwput.calls.append(args)
 
    monkeypatch.setitem(sys.modules, "constants", constants)
    monkeypatch.setitem(sys.modules, "CWPutData", cwput)
    return constants, cwput

@pytest.fixture
def alarm_table(aws):
    return boto3.resource("dynamodb").create_table(
        TableName="alarm-notifications",
        KeySchema=[
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "timestamp", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "timestamp", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

@pytest.fixture
def targets_table(aws):
    return boto3.resource("dynamodb").create_table(
        TableName="targets",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

@pytest.fixture
def crawler(aws, fake_deps, alarm_table, targets_table, monkeypatch):
    monkeypatch.setenv("ALARM_NOTIFICATIONS_TABLE", alarm_table.name)
    module = load_module(CRAWLER_FILE, "crawler_handler")
    module.targets_table = targets_table
    return module
 
 
@pytest.fixture
def crud(aws, targets_table, monkeypatch):
    monkeypatch.setenv("TARGETS_TABLE", targets_table.name)
    return load_module(CRUD_FILE, "crud_handler")