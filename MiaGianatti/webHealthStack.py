import json
from aws_cdk import (
    aws_lambda as _lambda,
    aws_events as events,
    aws_iam as iam,
    aws_sns as sns,
    aws_sns_subscriptions as subscriptions,
    aws_cloudwatch as cw,
    aws_cloudwatch_actions as cw_actions,
    aws_events_targets as targets,
    aws_dynamodb as DynamoDB,
    aws_apigateway as apigw,
    RemovalPolicy,
    Stack,
    Duration,
    CfnOutput,
)
from constructs import Construct
import constants

CRAWLER_TIMEOUT_SECONDS = 30
CRAWLER_MEMORY_MB = 256
OPS_NAMESPACE = "WebCrawler/Ops"

ROLLBACK_CODE = """
import json
import os
import boto3

lam = boto3.client("lambda")


def lambda_handler(event, context):
    fn = os.environ["FUNCTION_NAME"]
    alias = os.environ["ALIAS_NAME"]

    for record in event.get("Records", []):
        message = json.loads(record["Sns"]["Message"])
        if message.get("NewStateValue") != "ALARM":
            print("Ignoring non-ALARM state:", message.get("NewStateValue"))
            continue

        current = lam.get_alias(FunctionName=fn, Name=alias)["FunctionVersion"]

        versions = []
        paginator = lam.get_paginator("list_versions_by_function")
        for page in paginator.paginate(FunctionName=fn):
            for v in page["Versions"]:
                if v["Version"] != "$LATEST":
                    versions.append(int(v["Version"]))

        older = sorted(v for v in versions if v < int(current))
        if not older:
            print("No earlier version to roll back to; alias stays on", current)
            return {"rolled_back": False, "current": current}

        previous = str(older[-1])
        lam.update_alias(FunctionName=fn, Name=alias, FunctionVersion=previous)
        print(f"Rolled alias {alias} back from {current} to {previous} "
              f"(alarm: {message.get('AlarmName')})")
        return {"rolled_back": True, "from": current, "to": previous}

    return {"rolled_back": False}
"""


class WebHealthStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        #Defining a role and applying policies
        user_role = iam.Role(self, "User",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies = [
                iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchLambdaInsightsExecutionRolePolicy")
            ]
        )

        #Lambda function for CloudWatch
        self.func = _lambda.Function(
            self, "webHealthFunction",
            runtime = _lambda.Runtime.PYTHON_3_12,
            handler = "handler.lambda_handler",
            code = _lambda.Code.from_asset("lambda/crawler"),
            role = user_role,
            timeout = Duration.seconds(CRAWLER_TIMEOUT_SECONDS),
            memory_size=CRAWLER_MEMORY_MB,
            insights_version=_lambda.LambdaInsightsVersion.VERSION_1_0_229_0,
            current_version_options=_lambda.VersionOptions(
                removal_policy=RemovalPolicy.RETAIN,
            )
        )

        #Lambda Function for DynamoDB
        db_func = _lambda.Function(
            self, "writeToDynamo",
            runtime = _lambda.Runtime.PYTHON_3_12,
            handler = "handler.lambda_handler",
            code = _lambda.Code.from_asset("lambda/alarm_logger"),
            role = user_role
        )

        #Targets Table
        targets_table = DynamoDB.TableV2(self, "TARGETS_TABLE",
            partition_key=DynamoDB.Attribute(name="id", type=DynamoDB.AttributeType.STRING),
            removal_policy=RemovalPolicy.DESTROY
        )

        #Lambda Function for API
        api_func = _lambda.Function(
            self, "CrudFunction",
            runtime = _lambda.Runtime.PYTHON_3_12,
            handler = "handler.lambda_handler",
            code = _lambda.Code.from_asset("lambda/crud"),
            environment = {"TARGETS_TABLE": targets_table.table_name}
        )
        targets_table.grant_read_write_data(api_func)

        #Alias that points at the currently live version (rollback repoints this)
        alias = _lambda.Alias(
            self, "LiveAlias",
            alias_name="live",
            version=self.func.current_version,
        )

        #Rollback Lambda (replaces CodeDeploy, which isn't available in this account)
        rollback_func = _lambda.Function(
            self, "RollbackFunction",
            runtime = _lambda.Runtime.PYTHON_3_12,
            handler = "index.lambda_handler",
            code = _lambda.Code.from_inline(ROLLBACK_CODE),
            timeout = Duration.seconds(30),
            environment = {
                "FUNCTION_NAME": self.func.function_name,
                "ALIAS_NAME": alias.alias_name,
            },
        )
        rollback_func.add_to_role_policy(iam.PolicyStatement(
            actions=[
                "lambda:GetAlias",
                "lambda:UpdateAlias",
                "lambda:ListVersionsByFunction",
            ],
            resources=[
                self.func.function_arn,
                f"{self.func.function_arn}:*",
            ],
        ))
        rollback_func.apply_removal_policy(RemovalPolicy.DESTROY)

        #Schedule timer (invoke the alias only, so rollbacks actually change what runs)
        rule = events.Rule(self, "Rule",
            schedule=events.Schedule.rate(Duration.minutes(5))
        )
        rule.add_target(targets.LambdaFunction(alias))

        #Metrics and Alarms

        metricNames = [constants.METRIC_LATENCY, constants.METRIC_AVAILABILITY, constants.METRIC_RESPONSE_SIZE]
        urls = [constants.URL]

        alarm_config = {
            "AVAILABILITY": {
                "threshold" : 1,
                "comparison_operator" : cw.ComparisonOperator.LESS_THAN_THRESHOLD,
                "evaluation_periods" : 1
            },
            "LATENCY": {
                "threshold" : 0.15,
                "comparison_operator" : cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
                "evaluation_periods" : 1
            },
            "RESPONSE_SIZE": {
                "threshold": 5000,
                "comparison_operator" : cw.ComparisonOperator.LESS_THAN_THRESHOLD,
                "evaluation_periods" : 1
            }
        }

        metrics = {}
        alarms = {}

        for url in urls:
            for metric_name in metricNames:
                key = f"{url}:{metric_name}"
                metrics[key] = cw.Metric(
                    namespace=constants.NAMESPACE,
                    metric_name=metric_name,
                    dimensions_map={
                    "URL": url
                    }
                )
                config = alarm_config[metric_name]
                alarms[key] = cw.Alarm(
                    self, f"{metric_name} Alarm {url}",
                    metric = metrics[key],
                    threshold = config["threshold"],
                    comparison_operator = config["comparison_operator"],
                    evaluation_periods = config["evaluation_periods"]
                )

        #Creating notifications for the alarms (email + DynamoDB log)
        topic = sns.Topic(self, "Alarm Notifications")
        topic.add_subscription(subscriptions.EmailSubscription("22127341@student.westernsydney.edu.au"))
        topic.add_subscription(subscriptions.LambdaSubscription(db_func))

        #Separate topic for rollback: only the Lambda ops alarms trigger it, so a
        #target website being down never rolls back the crawler's code.
        rollback_topic = sns.Topic(self, "Rollback Notifications")
        rollback_topic.add_subscription(subscriptions.LambdaSubscription(rollback_func))

        ONE_MIN = Duration.minutes(1)

        errors_alarm = alias.metric_errors(period=ONE_MIN, statistic="Sum").create_alarm(
            self, "CrawlerErrors",
            threshold=1, evaluation_periods=1,
            comparison_operator=cw.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
        )

        throttles_alarm = alias.metric_throttles(period=ONE_MIN, statistic="Sum").create_alarm(
            self, "CrawlerThrottles",
            threshold=1, evaluation_periods=1,
            comparison_operator=cw.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
        )

        duration_alarm = alias.metric_duration(period=ONE_MIN, statistic="p95").create_alarm(
            self, "CrawlerDurationP95",
            threshold=CRAWLER_TIMEOUT_SECONDS * 1000 * 0.8,
            evaluation_periods=1,
            comparison_operator=cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
        )

        invocations_alarm = alias.metric_invocations(period=Duration.minutes(5), statistic="Sum").create_alarm(
            self, "CrawlerNoInvocations",
            threshold=1, evaluation_periods=3,
            comparison_operator=cw.ComparisonOperator.LESS_THAN_THRESHOLD,
            treat_missing_data=cw.TreatMissingData.BREACHING,
        )

        memory_metric = cw.Metric(
            namespace="LambdaInsights", metric_name="memory_utilization",
            dimensions_map={"function_name": self.func.function_name},
            statistic="Maximum", period=Duration.minutes(5),
        )

        memory_alarm = memory_metric.create_alarm(
            self, "CrawlerMemory",
            threshold=80, evaluation_periods=2,
            comparison_operator=cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
        )

        run_duration_alarm = cw.Metric(
            namespace=OPS_NAMESPACE, metric_name="RunDurationSeconds",
            statistic="Maximum", period=Duration.minutes(5),
        ).create_alarm(
            self, "CrawlerRunDuration",
            threshold=CRAWLER_TIMEOUT_SECONDS * 0.8, evaluation_periods=1,
            comparison_operator=cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
        )

        ops_alarms = [errors_alarm, throttles_alarm, duration_alarm,
                    invocations_alarm, memory_alarm, run_duration_alarm]
        for a in ops_alarms:
            a.add_alarm_action(cw_actions.SnsAction(topic))           # email + DynamoDB log
            a.add_alarm_action(cw_actions.SnsAction(rollback_topic))  # rollback
            a.apply_removal_policy(RemovalPolicy.DESTROY)

        for alarm in alarms.values():
            alarm.add_alarm_action(cw_actions.SnsAction(topic))

        #Logging alarm in DynamoDB
        table = DynamoDB.TableV2(self, "ALARM_NOTIFICATIONS_TABLE",
            partition_key=DynamoDB.Attribute(name="pk", type=DynamoDB.AttributeType.STRING),
            sort_key = DynamoDB.Attribute(name="timestamp", type=DynamoDB.AttributeType.STRING),
            removal_policy= RemovalPolicy.DESTROY
        )

        #Granting read access for the user
        table.grant_read_data(user_role)

        # Granting write access for the function
        table.grant_write_data(self.func)
        db_func.add_environment("ALARM_NOTIFICATIONS_TABLE", table.table_name)

        #Destroying the policy
        self.func.apply_removal_policy(RemovalPolicy.DESTROY)

        #Destroying DynamoDB function
        db_func.apply_removal_policy(RemovalPolicy.DESTROY)

        #Destroying the alarms
        for alarm in alarms.values():
            alarm.apply_removal_policy(RemovalPolicy.DESTROY)

        # Creating the dashboard on AWS CloudWatch
        dashboard = cw.Dashboard(self, "Web Health Dashboard",
        default_interval=Duration.days(7),
        variables=[cw.DashboardVariable(
                id="region2",
                type=cw.VariableType.PATTERN,
                label="RegionPattern",
                input_type=cw.VariableInputType.INPUT,
                value="us-east-1",
                default_value=cw.DefaultValue.value("us-east-1"),
                visible=True
            )
        ])

        for url in urls:
            def m(name, stat="Average"):
                return metrics[f"{url}:{name}"].with_(statistic=stat, period=Duration.minutes(5))

            lat_cfg = alarm_config["LATENCY"]
            avail_cfg = alarm_config["AVAILABILITY"]
            size_cfg = alarm_config["RESPONSE_SIZE"]

            dashboard.add_widgets(
                cw.TextWidget(markdown=f"## {url}", width=24, height=1),

                cw.SingleValueWidget(
                    title="Current availability / latency / size",
                    width=24, height=3,
                    metrics=[
                        m(constants.METRIC_AVAILABILITY, "Minimum"),
                        m(constants.METRIC_LATENCY),
                        m(constants.METRIC_RESPONSE_SIZE),
                    ],
                ),

                cw.GraphWidget(
                    title="Availability (1 = up)", width=8,
                    left=[m(constants.METRIC_AVAILABILITY, "Minimum")],
                    left_y_axis=cw.YAxisProps(min=0, max=1.2),
                    left_annotations=[cw.HorizontalAnnotation(
                        value=avail_cfg["threshold"], label="Alarm threshold", color="#d62728")],
                ),
                cw.GraphWidget(
                    title="Latency (seconds)", width=8,
                    left=[m(constants.METRIC_LATENCY), m(constants.METRIC_LATENCY, "Maximum")],
                    left_y_axis=cw.YAxisProps(min=0),
                    left_annotations=[cw.HorizontalAnnotation(
                        value=lat_cfg["threshold"], label="Alarm threshold", color="#d62728")],
                ),
                cw.GraphWidget(
                    title="Response size (bytes)", width=8,
                    left=[m(constants.METRIC_RESPONSE_SIZE)],
                    left_y_axis=cw.YAxisProps(min=0),
                    left_annotations=[cw.HorizontalAnnotation(
                        value=size_cfg["threshold"], label="Alarm threshold", color="#d62728")],
                ),
            )

        dashboard.add_widgets(
            cw.AlarmStatusWidget(
                title="Alarm status", width=24, height=4,
                alarms=list(alarms.values()) + ops_alarms,
            )
        )

        dashboard.add_widgets(
            cw.GraphWidget(title="Invocations / Errors / Throttles", width=12,
                left=[alias.metric_invocations(), alias.metric_errors(), alias.metric_throttles()]),
            cw.GraphWidget(title="Duration (avg / p95)", width=12,
                left=[alias.metric_duration(), alias.metric_duration(statistic="p95")]),
            cw.GraphWidget(title="Memory utilization %", width=12, left=[memory_metric]),
            cw.GraphWidget(title="Run duration (s)", width=12,
                left=[cw.Metric(namespace=OPS_NAMESPACE, metric_name="RunDurationSeconds")]),
        )

        #REST API
        api = apigw.RestApi(self, "TargetsApi",
        rest_api_name="Crawler Targets API",
            deploy_options=apigw.StageOptions(
                stage_name="prod",
                throttling_rate_limit=10,
                throttling_burst_limit=20,
            ),
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
            ),
        )

        integration = apigw.LambdaIntegration(api_func)

        targets_resource = api.root.add_resource("targets")
        targets_resource.add_method("GET", integration)
        targets_resource.add_method("POST", integration)

        target_resource = targets_resource.add_resource ("{id}")
        target_resource.add_method("GET", integration)
        target_resource.add_method("PUT", integration)
        target_resource.add_method("DELETE", integration)

        CfnOutput(self, "TargetsApiUrl", value=api.url)

        #Crawler reads list
        targets_table.grant_read_data(self.func)
        self.func.add_environment("TARGETS_TABLE", targets_table.table_name)