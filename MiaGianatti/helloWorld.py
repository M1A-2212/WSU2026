import aws_cdk as cdk

def lambda_handler(event, context):
    print("Hello world")

rule = events.Rule(self, "Rule",
    schedule=events.Schedule.rate(cdk.Duration.minutes(5))
)

# apply_removal_policy(RemovalPolicy.DESTROY)