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
        self.func = _lambda.Function(
            self, "helloFunction",
            runtime = _lambda.Runtime.PYTHON_3_12,
            handler = "handler.lambda_handler",
            code = _lambda.Code.from_asset("lambda"),
            role = user_role
        )

        #Schedule timer
        rule = events.Rule(self, "Rule",
        schedule=events.Schedule.rate(Duration.minutes(5))
        )

        rule.add_target(targets.LambdaFunction(self.func))

        #Metrics and Alarms

        metricNames = [constants.METRIC_LATENCY, constants.METRIC_AVAILABILITY, constants.METRIC_RESPONSE_SIZE]
        urls = [constants.URL]

        alarm_config = {
            "AVAILABILITY": {
                "threshold" : 1,
                "comparison_operator" : cw.ComparisonOperator.LESS_THAN_THRESHOLD,
                "evaluation_periods" : 1
            },
            "LATENCY": {
                "threshold" : 0.15,
                "comparison_operator" : cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
                "evaluation_periods" : 1
            },
            "RESPONSE_SIZE": {
                "threshold": 1,
                "comparison_operator" : cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
                "evaluation_periods" : 1
            }
        }

        metrics = {}
        alarms = {}

        for url in urls:
            for metric_name in metricNames:
                key = f"{url}:{metric_name}"
                metrics[key] = cw.Metric(
                    namespace=constants.NAMESPACE,
                    metric_name=metric_name,
                    dimensions_map={
                    "URL": url
                    }
                )
                config = alarm_config[metric_name]
                alarms[key] = cw.Alarm(
                    self, f"{metric_name} Alarm {url}",
                    metric = metrics[key],
                    threshold = config["threshold"],
                    comparison_operator = config["comparison_operator"],
                    evaluation_periods = config["evaluation_periods"]
                )

        dashboard = cw.Dashboard(self, "Dash",
        default_interval=Duration.days(7),
        variables=[cw.DashboardVariable(
                id="region2",
                type=cw.VariableType.PATTERN,
                label="RegionPattern",
                input_type=cw.VariableInputType.INPUT,
                value="us-east-1",
                default_value=cw.DefaultValue.value("us-east-1"),
                visible=True
            )
        ]
)


        #Destroying the policy
        self.func.apply_removal_policy(RemovalPolicy.DESTROY)