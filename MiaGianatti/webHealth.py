import json
from aws_cdk import (
    aws_lambda as _lambda,
    aws_events as events,
    aws_events_targets as targets,
    RemovalPolicy
)

def lambda_handler(event, context):
    result = helloFunction()

def helloFunction():
    print ("Hello World")

rule = events.Rule(self, "Rule",
    schedule=events_.Schedule.rate(cdk.Duration.minutes(5))
)
#rule.add_target(targets.LambdaFunction())

result.apply_removal_policy(RemovalPolicy.DESTROY)