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
            managedPolicy = [iam.ManagedPolicy.from_Aws_Managed_Policy_Name("CloudWatchFullAccess")]
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

        #Destroying the policy
        greetingFunction.apply_removal_policy(RemovalPolicy.DESTROY)

        #Metrics and Alarms
        #for()
        #fix up C., might not be the right part 

        latencyMetric = cw.Metric(
        namespace= C.namespace,
        metric_name= C.metricLatency,
            dimensions_map={
                "URL": C.URL
            }
        )

        availabilityMetric = cw.Metric(
        namespace= C.namespace,
        metric_name= C.metricAvailability,
            dimensions_map={
                "URL": C.URL
            }
        )

        availabilityAlarm = cw.Alarm(self, "Availability Alarm",
            metric=availabilityMetric,
            threshold = 1,
            comparison_operator = cw.ComparisonOperator.LESS_THAN_THRESHOLD
        )

        latencyAlarm = cw.Alarm(self, "Latency Alarm",
            metric=latencyMetric,
            threshold = 0.25,
            comparison_operator = cw.ComparisonOperator.GREATER_THAN_THRESHOLD
        )