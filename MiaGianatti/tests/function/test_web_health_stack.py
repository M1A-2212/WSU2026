import aws_cdk as cdk
import pytest
import responses
import aws_cdk as core
import aws_cdk.assertions as assertions
import json

from aws_cdk.assertions import Match, Template 
from webHealthStack import WebHealthStack

@pytest.fixture
def template():
    app = core.App()
    stack = WebHealthStack(app, "WebHealthStack")
    return assertions.Template.from_stack(stack)

@pytest.fixture
def aws_credentials(monkeypatch):
    for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
          monkeypatch.setenv(k, "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")

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

        
def make_sns_event(alarm_name="LATENCY Alarm https://example.com", new_state="ALARM"):
    message = {
        "AlarmName": alarm_name,
        "NewStateValue": new_state,
        "StateChangeTime": "2024-01-01T00:00:00.000Z",
    }
    return {
        "Records": [
            {
                "EventSource": "aws:sns",
                "Sns": {
                    "Message": json.dumps(message),
                    "Timestamp": "2024-01-01T00:00:00.000Z",
                },
            }
        ]
    }

# Function Tests
def test_role_is_assumable_by_lambda_and_has_cloudwatch_access(template):
    roles = template.find_resources("AWS::IAM::Role")
    assert any(
        "CloudWatchFullAccess" in json.dumps(r["Properties"].get("ManagedPolicyArns", []))
        for r in roles.values()
    )
    template.has_resource_properties(
        "AWS::IAM::Role",
        {
            "AssumeRolePolicyDocument": {
                "Statement": [
                    {"Action": "sts:AssumeRole", "Effect": "Allow",
                     "Principal": {"Service": "lambda.amazonaws.com"}}
                ]
            }
        },
    )

def test_role_can_read_and_write_alarm_table(template):
    template.has_resource_properties(
        "AWS::IAM::Policy",
        {
            "PolicyDocument": {
                "Statement": Match.array_with(
                    [
                        Match.object_like({"Action": Match.array_with(["dynamodb:GetItem"])}),
                        Match.object_like({"Action": Match.array_with(["dynamodb:PutItem"])}),
                    ]
                )
            }
        },
    )

@responses.activate
def test_health_check_runs_every_five_minutes(template):
    template.has_resource_properties(
        "AWS::Events::Rule",
        {
            "ScheduleExpression": "rate(5 minutes)",
            "Targets": Match.array_with([Match.object_like({"Arn": Match.any_value()})]),
        },
    )