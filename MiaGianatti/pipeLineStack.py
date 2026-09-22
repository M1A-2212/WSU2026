from aws_cdk import (
    pipelines as _pipelines,
    Stack,
    SecretValue,
    aws_codepipeline_actions,
    Stage
)

from constructs import Construct

from pipelineStage import thePipeLineStage

class PipeLineStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None: 
        super().__init__(scope, construct_id, **kwargs)

        source = _pipelines.CodePipelineSource.git_hub (
            repo_string = "WSU2026/MiaGianatti",
            branch = "main",
            authentication = SecretValue.secrets_manager("gitHubSecret"),
            trigger = aws_codepipeline_actions.GitHubTrigger ("POLL")
        )

        synth = _pipelines.ShellStep(
            id = "Synth",
            input= source,
            commands = [
                "npm install -g aws-cdk",
                "cd MiaGianatti", 
                "pip install -r requirements.txt",
                "cdk synth"
            ],
            primary_output_directory = "MiaGianatti/cdk.out"
        )

        pipeline = _pipelines.CodePipeline(self,
            id = "PipeLine",
            synth = synth
        )

        #Unit Tests
        alphaStage = thePipeLineStage(self, "AlphaTests")
        pipeline.add_stage(alphaStage,
            post=[_pipelines.ShellStep("unitTests",
                commands=[
                    "npm install -g aws-cdk",
                    "cd MiaGianatti", 
                    "pip install -r requirements.txt",
                    "cdk synth"
                ]
            )]
        )

        #Function Tests
        betaStage = thePipeLineStage(self, "BetaTests")
        pipeline.add_stage(
            stage = betaStage,
            post = [_pipelines.ShellStep("functionTests",
                commands=[
                    "npm install -g aws-cdk",
                    "cd MiaGianatti", 
                    "pip install -r requirements.txt",
                    "cdk synth"
                ]
            )]
        )

        #Integration Tests
        gammaStage = thePipeLineStage(self, "GammaTests")
        pipeline.add_stage(
            stage = gammaStage,
            post = [_pipelines.ShellStep("integrationTests",
                commands=[
                    "npm install -g aws-cdk",
                    "cd MiaGianatti", 
                    "pip install -r requirements.txt",
                    "cdk synth"
                ]
            )]
        )

        prod = thePipeLineStage(self, "ProductionStage")
        pipeline.add_stage(
            stage = prod,
            pre = [_pipelines.ManualApprovalStep("PromoteToProd")]
        )