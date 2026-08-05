import json
from aws_cdk import (
    aws_lambda as _lambda,
    aws_events as events,
    aws_events_targets as targets,
    RemovalPolicy,
    Duration
)
class webHealth(Construct):
    def __init__(self, scope: Construct):

        self.func = _lambda.Function(
            self, "helloFunction",
            runtime = _lambda.Runtime.PYTHON_3_14,
            handler = "handler.lambda_handler",
            code = _lambda.Code.from_asset("lambda"),
        )

        rule = events.Rule(self, "Rule",
        schedule=events.Schedule.rate(cdk.Duration.minutes(5))
        )
        rule.add_target(targets.LambdaFunction(self.func))

        result.apply_removal_policy(RemovalPolicy.DESTROY)