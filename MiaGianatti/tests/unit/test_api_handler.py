import json

import pytest

from tests.helpers import api_event
from tests.unit.conftest import FakeConditionalCheckFailed


def body_of(resp):
    return json.loads(resp["body"]) if resp["body"] else None

def test_routes_get_collection_to_list(crud):
    crud.table.scan.return_value = {"Items": []}
    assert crud.lambda_handler(api_event("GET"), None)["statusCode"] == 200
    crud.table.scan.assert_called_once()


def test_routes_get_with_id_to_get_item(crud):
    crud.table.get_item.return_value = {"Item": {"id": "1"}}
    crud.lambda_handler(api_event("GET", "1"), None)
    crud.table.get_item.assert_called_once_with(Key={"id": "1"})