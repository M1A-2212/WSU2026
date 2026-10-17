import json
import time
from datetime import datetime, timedelta, timezone
import boto3
import pytest
from boto3.dynamodb.conditions import Key
 
import constants

pytestmark = pytest.mark.integration

STACK_NAME = "WebHealthStack"

@pytest.fixture(scope="session")
def aws():
    return boto3.Session(region_name="us-east-1")

@pytest.fixture(scope="session")
def stack_name():
    return STACK_NAME

@pytest.fixture(scope="session")
def health_function(aws, stack_name):
    cfn = aws.client("cloudformation")
    resources = cfn.describe_stack_resources(StackName=stack_name)["StackResources"]
    fns = [r for r in resources if r["ResourceType"] == "AWS::Lambda::Function"]
    # pick the health-check lambda by logical ID; adjust the substring to match yours
    match = next(r for r in fns if "Health" in r["LogicalResourceId"])
    return match["PhysicalResourceId"]

@pytest.fixture
def aws_credentials(monkeypatch):
    for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
          monkeypatch.setenv(k, "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")

ENV_VAR_BUG = pytest.mark.xfail(
    strict=True,
    reason="BUG: ALARM_NOTIFICATIONS_TABLE is only set on writeToDynamo, so the health-check "
           "function raises KeyError on import. Remove this marker once fixed.",
)
SNS_SOURCE_BUG = pytest.mark.xfail(
    strict=True,
    reason="BUG: handler compares EventSource to 'aws.sns' instead of 'aws:sns', so SNS alarms "
           "are never written to DynamoDB. Remove this marker once fixed.",
)
 
 
def wait_for(predicate, timeout=180, interval=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(interval)
    return None

@pytest.mark.integration
def test_stack_is_deployed(aws, stack_name):
    status = aws.client("cloudformation").describe_stacks(StackName=stack_name)["Stacks"][0]["StackStatus"]
    assert status in ("CREATE_COMPLETE", "UPDATE_COMPLETE")
 


@pytest.mark.integration
@ENV_VAR_BUG
def test_health_check_metrics_reach_cloudwatch(aws, health_function):
    aws.client("lambda").invoke(FunctionName=health_function, Payload=b"{}")
    cw = aws.client("cloudwatch")
 
    def datapoints():
        now = datetime.now(timezone.utc)
        return cw.get_metric_statistics(
            Namespace=constants.NAMESPACE,
            MetricName=constants.METRIC_AVAILABILITY,
            Dimensions=[{"Name": "URL", "Value": constants.URL}],
            StartTime=now - timedelta(minutes=15),
            EndTime=now + timedelta(minutes=1),
            Period=60,
            Statistics=["Maximum"],
        )["Datapoints"]
 
    assert wait_for(datapoints), "no availability datapoint appeared within 3 minutes"