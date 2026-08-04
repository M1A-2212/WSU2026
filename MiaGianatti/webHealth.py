import json
import aws_cdk as cdk

def lambda_handler(event, context):
    greeting_target = print ("Hello World")

rule = events.Rule(self, "Rule",
    schedule=events_.Schedule.rate(cdk.Duration.minutes(5))
)

# apply_removal_policy(RemovalPolicy.DESTROY)