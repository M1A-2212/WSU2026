import json
from aws_cdk import (
    aws_lambda as _lambda,
    aws_events as events,
    aws_events_targets as targets,
    RemovalPolicy,
    Stack,
    Duration
)
from constructs import Construct

class WebHealthStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None: 
        super().__init__(scope, construct_id, **kwargs)

        _lambda.Function(
            self, "helloFunction",
            runtime = _lambda.Runtime.PYTHON_3_14,
            handler = "handler.lambda_handler",
            code = _lambda.Code.from_asset("lambda"),
        )

        rule = events.Rule(self, "Rule",
        schedule=events.Schedule.rate(Duration.minutes(5))
        )
        rule.add_target(targets.LambdaFunction(self.func))

        result.apply_removal_policy(RemovalPolicy.DESTROY)