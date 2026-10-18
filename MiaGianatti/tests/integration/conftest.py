import boto3
import pytest
from moto import mock_aws

from tests.helpers import load_lambda


@pytest.fixture
def system():
    with mock_aws():
        ddb = boto3.resource("dynamodb")
        ddb.create_table(TableName="targets-test", BillingMode="PAY_PER_REQUEST",
                         KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
                         AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}])
        ddb.create_table(TableName="alarms-test", BillingMode="PAY_PER_REQUEST",
                         KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"},
                                    {"AttributeName": "timestamp", "KeyType": "RANGE"}],
                         AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"},
                                               {"AttributeName": "timestamp", "AttributeType": "S"}])
        yield type("System", (), {
            "crawler": load_lambda("crawler"),
            "crud": load_lambda("crud"),
            "alarm_logger": load_lambda("alarm_logger"),
            "alarms_table": ddb.Table("alarms-test"),
        })
