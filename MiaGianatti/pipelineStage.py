import json
from aws_cdk import (
    Stage  
)
from constructs import Construct
import constants
from webHealthStack import WebHealthStack

class thePipeLineStage(Stage):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None: 
        super().__init__(scope, construct_id, **kwargs)

        ApplicationStack=WebHealthStack(self, "APP")