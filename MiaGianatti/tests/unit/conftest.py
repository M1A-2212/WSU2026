from unittest.mock import MagicMock, patch

import pytest

from tests.helpers import load_lambda

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

class FakeConditionalCheckFailed(Exception):
    """Stands in for DynamoDB's ConditionalCheckFailedException."""


@pytest.fixture
def crawler():
    with patch("boto3.client") as client, patch("boto3.resource") as resource:
        module = load_lambda("crawler")
    module.cw_client = client.return_value
    module.targets_table = resource.return_value.Table.return_value
    module.CWPutData = MagicMock()
    return module


@pytest.fixture
def cw_put_data():
    import importlib.util
    from tests.helpers import LAMBDA_DIRS
    with patch("boto3.client") as client:
        spec = importlib.util.spec_from_file_location("CWPutData_unit", LAMBDA_DIRS["crawler"] / "CWPutData.py")
        module = importlib.util.module_from_spec(spec)
        import sys
        sys.path.insert(0, str(LAMBDA_DIRS["crawler"]))
        try:
            spec.loader.exec_module(module)
        finally:
            sys.path.remove(str(LAMBDA_DIRS["crawler"]))
            sys.modules.pop("constants", None)
    module.client = client.return_value
    return module


@pytest.fixture
def alarm_logger():
    with patch("boto3.resource") as resource:
        module = load_lambda("alarm_logger")
    module.table = resource.return_value.Table.return_value
    return module


@pytest.fixture
def crud():
    with patch("boto3.resource") as resource:
        table = resource.return_value.Table.return_value
        table.meta.client.exceptions.ConditionalCheckFailedException = FakeConditionalCheckFailed
        module = load_lambda("crud")
    module.table = table
    return module