import aws_cdk as core
import aws_cdk.assertions as assertions

from webHealthStack import WebHealthStack

# example tests. To run these tests, uncomment this file along with the example
# resource in mia_gianatti/mia_gianatti_stack.py
def test_lambda_created():
    app = core.App()
    stack = WebHealthStack(app, "WebHealthStack")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#    })

    template.resource_properties_count_is("AWS::Lambda::Function",2)
