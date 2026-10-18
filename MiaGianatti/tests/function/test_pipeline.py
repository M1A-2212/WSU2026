import io
import json
import sys
import types
import zipfile

import boto3
import pytest

from tests.helpers import REPO_ROOT, sns_alarm_event

TRUST = json.dumps({"Version": "2012-10-17", "Statement": [{
    "Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}]})


def _zip(source):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("handler.py", source)
    return buf.getvalue()


@pytest.fixture
def lam(aws):
    return boto3.client("lambda")


@pytest.fixture
def crawler_fn(lam):
    """crawler-fn with versions 1..3 and alias 'live' on 3."""
    role = boto3.client("iam").create_role(RoleName="r", AssumeRolePolicyDocument=TRUST)["Role"]["Arn"]
    lam.create_function(FunctionName="crawler-fn", Runtime="python3.12", Role=role,
                        Handler="handler.lambda_handler", Code={"ZipFile": _zip("x = 0")})
    for n in range(1, 4):
        lam.update_function_code(FunctionName="crawler-fn", ZipFile=_zip(f"x = {n}"))
        lam.publish_version(FunctionName="crawler-fn")
    lam.create_alias(FunctionName="crawler-fn", Name="live", FunctionVersion="3")
    return lam


@pytest.fixture
def rollback(aws):
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from webHealthStack import ROLLBACK_CODE
    finally:
        sys.path.remove(str(REPO_ROOT))
    module = types.ModuleType("rollback_inline_functional")
    exec(ROLLBACK_CODE, module.__dict__)
    return module


def alias_version(lam):
    return lam.get_alias(FunctionName="crawler-fn", Name="live")["FunctionVersion"]


def test_alarm_moves_alias_to_previous_version(crawler_fn, rollback):
    result = rollback.lambda_handler(sns_alarm_event(), None)
    assert result == {"rolled_back": True, "from": "3", "to": "2"}
    assert alias_version(crawler_fn) == "2"


def test_repeated_alarms_keep_stepping_back_until_the_first_version(crawler_fn, rollback):
    for expected in ["2", "1"]:
        rollback.lambda_handler(sns_alarm_event(), None)
        assert alias_version(crawler_fn) == expected
    result = rollback.lambda_handler(sns_alarm_event(), None)
    assert result["rolled_back"] is False
    assert alias_version(crawler_fn) == "1"