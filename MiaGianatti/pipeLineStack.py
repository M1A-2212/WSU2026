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
            repo_string = "M1A-2212/WSU2026",
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

        SETUP = [
            "cd MiaGianatti",
            "pip install -r requirements.txt",
            "pip install pytest",
        ]

        def test_step(step_id, pytest_args):
            return _pipelines.ShellStep(
                step_id,
                input=source,
                commands=[*SETUP, f"python -m pytest {pytest_args} -v"],
            )

        #Unit Tests
        alphaStage = thePipeLineStage(self, "AlphaTests")
        pipeline.add_stage(alphaStage,
            post=[test_step(
                "unitTests", 
                "tests/unit/test_webHealthStack.py"
            )]
        )

        #Function Tests
        betaStage = thePipeLineStage(self, "BetaTests")
        pipeline.add_stage(
            stage = betaStage,
            post=[test_step(
                "functionTests",
                "tests/unit/test_crawler_handler.py tests/test_api_handler.py"
            )]
        )

        #Integration Tests
        gammaStage = thePipeLineStage(self, "GammaTests")
        pipeline.add_stage(
            stage = gammaStage,
            post=[test_step(
                "functionTests",
                "tests/unit/test_deployment.py"
            )]
        )

        prod = thePipeLineStage(self, "ProductionStage")
        pipeline.add_stage(
            stage = prod,
            pre = [_pipelines.ManualApprovalStep("PromoteToProd")]
        )