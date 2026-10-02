import os
import responses
import aws_cdk as core
import aws_cdk.assertions as assertions
import boto3
import pytest
from moto import mock_aws

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))

os.environ.setdefault("ALARM_NOTIFICATIONS_TABLE", "test-table")

from webHealthStack import WebHealthStack
import constants
import handler

from unittest.mock import patch, MagicMock

# example tests. To run these tests, uncomment this file along with the example
#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#    })

@pytest.fixture
def template():
    app = core.App()
    stack = WebHealthStack(app, "WebHealthStack")
    return assertions.Template.from_stack(stack)


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
@responses.activate
def test_health_check_publishes_metrics(monkeypatch, cloudwatch_client):
    test_url = "https://www.google.com"
    monkeypatch.setattr("handler.constants.URL", test_url)

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = b"OK"

    with patch("handler.urllib.request.urlopen", return_value=mock_response):
        result = handler.lambda_handler({}, {})

    assert result["statusCode"] == 200

    metrics = cloudwatch_client.list_metrics(Namespace=constants.NAMESPACE)
    metric_names = {m["MetricName"] for m in metrics["Metrics"]}

    assert constants.METRIC_AVAILABILITY in metric_names
    assert constants.METRIC_LATENCY in metric_names
    assert constants.METRIC_RESPONSE_SIZE in metric_names


# Integration Tests