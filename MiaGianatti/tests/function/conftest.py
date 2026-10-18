import boto3
import pytest
import threading

from moto import mock_aws
from http.server import BaseHTTPRequestHandler, HTTPServer
from tests.helpers import load_lambda, metric_value

@pytest.fixture(autouse=True)
def _aws_env(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("TARGETS_TABLE", "targets-test")
    monkeypatch.setenv("ALARM_NOTIFICATIONS_TABLE", "alarms-test")
    monkeypatch.setenv("FUNCTION_NAME", "crawler-fn")
    monkeypatch.setenv("ALIAS_NAME", "live")

@pytest.fixture
def aws():
    with mock_aws():
        yield


def _table(name, key_schema, attrs):
    ddb = boto3.resource("dynamodb")
    return ddb.create_table(
        TableName=name, KeySchema=key_schema, AttributeDefinitions=attrs, BillingMode="PAY_PER_REQUEST")


@pytest.fixture
def targets_table(aws):
    return _table("targets-test",
                  [{"AttributeName": "id", "KeyType": "HASH"}],
                  [{"AttributeName": "id", "AttributeType": "S"}])


@pytest.fixture
def alarms_table(aws):
    return _table("alarms-test",
                  [{"AttributeName": "pk", "KeyType": "HASH"}, {"AttributeName": "timestamp", "KeyType": "RANGE"}],
                  [{"AttributeName": "pk", "AttributeType": "S"}, {"AttributeName": "timestamp", "AttributeType": "S"}])


@pytest.fixture
def crawler(targets_table):
    return load_lambda("crawler")


@pytest.fixture
def crud(targets_table):
    return load_lambda("crud")


@pytest.fixture
def alarm_logger(alarms_table):
    return load_lambda("alarm_logger")


@pytest.fixture
def read_metric():
    return metric_value

def pytest_collection_modifyitems(items):
    """Tag each test with the marker for its folder."""
    for item in items:
        path = str(item.fspath).replace("\\", "/")
        for kind in ("unit", "function", "integration"):
            if f"/tests/{kind}/" in path:
                item.add_marker(getattr(pytest.mark, kind))


class _Site(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/ok":
            body = b"a" * 6000
            self.send_response(200)
        elif self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/ok")
            body = b""
        elif self.path == "/created":
            body = b"made"
            self.send_response(201)
        else:
            body = b"missing"
            self.send_response(404 if self.path == "/missing" else 500)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture(scope="session")
def site():
    server = HTTPServer(("127.0.0.1", 0), _Site)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
