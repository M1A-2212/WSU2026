import aws_cdk as core
import aws_cdk.assertions as assertions

from mia_gianatti.mia_gianatti_stack import MiaGianattiStack

# example tests. To run these tests, uncomment this file along with the example
# resource in mia_gianatti/mia_gianatti_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = MiaGianattiStack(app, "mia-gianatti")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
