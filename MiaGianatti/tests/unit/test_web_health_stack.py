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

# Unit Tests
def test_lambda_created():
    app = core.App()
    stack = WebHealthStack(app, "WebHealthStack")
    template = assertions.Template.from_stack(stack)
    template.resource_count_is("AWS::Lambda::Function", 4)

def test_lambda_runtime():
    app = core.App()
    stack = WebHealthStack(app, "WebHealthStack")
    template = assertions.Template.from_stack(stack)
    template.has_resource_properties("AWS::Lambda::Function", {
        "Runtime": "python3.12"
    })

def test_lambda_handler():
    app = core.App()
    stack = WebHealthStack(app, "WebHealthStack")
    template = assertions.Template.from_stack(stack)
    template.has_resource_properties("AWS::Lambda::Function", {
        "Handler": "handler.lambda_handler"
    })

def test_eventbridge_rule_count():
    app = core.App()
    stack = WebHealthStack(app, "WebHealthStack")
    template = assertions.Template.from_stack(stack)
    template.resource_count_is("AWS::Events::Rule", 1)

def test_eventbridge_rule_schedule():
    app = core.App()
    stack = WebHealthStack(app, "WebHealthStack")
    template = assertions.Template.from_stack(stack)
    template.has_resource_properties("AWS::Events::Rule", {
        "ScheduleExpression": "rate(5 minutes)",
        "State": "ENABLED"
    })

def test_dynamodb_table_count():
    app = core.App()
    stack = WebHealthStack(app, "WebHealthStack")
    template = assertions.Template.from_stack(stack)
    template.resource_count_is("AWS::DynamoDB::GlobalTable", 2)
    

def test_alarm_count():
    app = core.App()
    stack = WebHealthStack(app, "WebHealthStack")
    template = assertions.Template.from_stack(stack)
    template.resource_count_is("AWS::CloudWatch::Alarm", 9)

def test_sns_subscription_count():
    app = core.App()
    stack = WebHealthStack(app, "WebHealthStack")
    template = assertions.Template.from_stack(stack)
    template.resource_count_is("AWS::SNS::Subscription", 3)

def test_sns_lambda_subscription_():
    app = core.App()
    stack = WebHealthStack(app, "WebHealthStack")
    template = assertions.Template.from_stack(stack)
    template.has_resource_properties("AWS::SNS::Subscription", {
        "Protocol": "lambda"
    })

def test_dashboard_created():
    app = core.App()
    stack = WebHealthStack(app, "WebHealthStack")
    template = assertions.Template.from_stack(stack)
    template.resource_count_is("AWS::CloudWatch::Dashboard", 1)    
