import json
from aws_cdk import (
    aws_lambda as _lambda,
    aws_events as events,
    aws_iam as iam,
    aws_cloudwatch as cw,
    aws_events_targets as targets,
    RemovalPolicy,
    Stack,
    Duration
)
from constructs import Construct
import constants

class WebHealthStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None: 
        super().__init__(scope, construct_id, **kwargs)

        #Defining a role and applying policies
        user_role = iam.Role(self, "User",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies = [
                iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchFullAccess")
            ]
        )

        #Hello World function
        greetingFunction = _lambda.Function(
            self, "helloFunction",
            runtime = _lambda.Runtime.PYTHON_3_12,
            handler = "handler.lambda_handler",
            code = _lambda.Code.from_asset("lambda"),
        )

        #Schedule timer
        rule = events.Rule(self, "Rule",
        schedule=events.Schedule.rate(Duration.minutes(5))
        )

        rule.add_target(targets.LambdaFunction(self.func))

        #Metrics and Alarms

        metricNames = [C.metricLatency, C.metricAvailability, C.metricResponseSize]
        urls = [C.URL]

        alarm_config = {
            "Availability": {
                "threshold" : 1,
                "comparison_operator" : cw.ComparisonOperator.LESS_THAN_THRESHOLD
            },
            "Latency": {
                "threshold" : 0.15,
                "comparision_operator" : cw.ComparisonOperator.GREATER_THAN_THRESHOLD
            },
            "Response Size": {
                "threshold": 1,
                "comparison_operator" : cw.ComparisonOperator.GREATER_THAN_THRESHOLD
            }
        }

        metrics = {}
        alarms = {}

        for url in urls:
            for metricName in metricNames:
                key = f"{url}:{metricName}"
                metrics[key] = cw.Metric(
                    namespace=C.namespace,
                    metricName=metricName,
                    dimensions_map={
                    "URL": C.URL
                    }
                )
                config = alarm_config[metricName]
                alarms[key] = cw.Alarm(
                    self, f"{metricName} Alarm {url}",
                    metric = metrics[key],
                    threshold = config["threshold"],
                    comparision_operator = config["comparison_operator"]
                )


        #Destroying the policy
        greetingFunction.apply_removal_policy(RemovalPolicy.DESTROY)