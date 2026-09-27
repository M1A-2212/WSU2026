import responses
import aws_cdk as core
import aws_cdk.assertions as assertions

import sys
import os
from webHealthStack import WebHealthStack

# example tests. To run these tests, uncomment this file along with the example
#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#    })

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
def tests_successful_health_metric_publish():
    test_url = "https://www.google.com"
    responses.add(responses.GET, test_url, body="OK", status=200)

    monkeypatch.setattr("handler.URL", test_url, raising=False)

    event = {}
    context = {}

    handler.lambda_handler(event, context)

    result = cloudwatch_client.list_metrics(Namespace="WebHealthStack")
    metric_names = {m["MetricName"] for m in result["Metrics"]}

    assert "AVAILABILITY" in metric_names
    assert "LATENCY" in metric_names
    assert "RESPONSE_SIZE" in metric_names



# Integration Tests