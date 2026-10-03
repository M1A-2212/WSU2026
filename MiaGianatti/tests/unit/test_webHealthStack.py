import os
os.environ.setdefault("ALARM_NOTIFICATIONS_TABLE", "test-table")

import responses
import aws_cdk as core
import aws_cdk.assertions as assertions
from aws_cdk.assertions import Match, Template
import boto3
import pytest
from moto import mock_aws
import json

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))

from webHealthStack import WebHealthStack
import constants
import handler

# example tests. To run these tests, uncomment this file along with the example
#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#    })

@pytest.fixture
def template():
    app = core.App()
    stack = WebHealthStack(app, "WebHealthStack")
    return assertions.Template.from_stack(stack)


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
    template.resource_count_is("AWS::Lambda::Function", 2)

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
    template.resource_count_is("AWS::DynamoDB::GlobalTable", 1)
    

def test_alarm_count():
    app = core.App()
    stack = WebHealthStack(app, "WebHealthStack")
    template = assertions.Template.from_stack(stack)
    template.resource_count_is("AWS::CloudWatch::Alarm", 3)

def test_sns_subscription_count():
    app = core.App()
    stack = WebHealthStack(app, "WebHealthStack")
    template = assertions.Template.from_stack(stack)
    template.resource_count_is("AWS::SNS::Subscription", 2)

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

# @responses.activate
# def test_health_check_runs_every_five_minutes(template):
#     template.has_resource_properties(
#         "AWS::Events::Rule",
#         {
#             "ScheduleExpression": "rate(5 minutes)",
#             "Targets": Match.array_with([Match.object_like({"Arn": Match.any_value()})]),
#         },
#     )

# def test_writes_alarm_record_to_database(ALARM_NOTIFICATIONS_TABLE):
#     event = make_sns_event()
#     handler.lambda_handler(event, {})

#     dynamo = boto3.client("dynamodb", region_name="us-east-1")
#     scan = dynamo.scan(TableName = ALARM_NOTIFICATIONS_TABLE)

#     assert scan["Count"] == 1
#     item = scan["Items"][0]
#     assert "pk" in item
#     assert "timestamp" in item

# Integration Tests