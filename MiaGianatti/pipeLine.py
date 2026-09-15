from aws_cdk import (
    pipelines as _pipelines,
    Stack,
    SecretValue,
    aws_codepipeline_actions
)

from constructs import Construct

class PipeLineStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None: 
        super().__init__(scope, construct_id, **kwargs)

        source = _pipelines.CodePipelineSource.git_hub (
            repo_string = ("Ayeshaomer/WSU2026", "main"),
            branch = "main",
            authentication = SecretValue.secrets_manager("gitHubSecret"),
            trigger = aws_codepipeline_actions.GitHubTrigger ("POLL")
        )

        synth=pipelines.ShellStep(
                id = "Synth",
                input= source,
                commands = [
                    "npm install -g aws-cdk",
                    "cd /MiaGianatti", 
                    "pip install -r requirements.txt",
                    "cdk synth"
                ],
               primary_output_directory = "MiaGianatti/cdk.out"
        )

        pipeline = pipelines.CodePipeline(self,
            id = "PipeLine",
            code_pipeline=code_pipeline
        )

        # Make a token and secret for this to actually work
        # aws secretsmanager create-secret --name gitHubSecret --secret-string <hash>