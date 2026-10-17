import json
import time
 
import pytest

def event(method, target_id=None, body=None, raw_body=None):
    if raw_body is None and body is not None:
        raw_body = json.dumps(body)
    return {
        "httpMethod": method,
        "pathParameters": {"id": target_id} if target_id else None,
        "body": raw_body,
    }
 
 
def call(crud, *args, **kwargs):
    r = crud.lambda_handler(event(*args, **kwargs), None)
    return r["statusCode"], (json.loads(r["body"]) if r["body"] else None), r
 
 
@pytest.fixture
def seeded(crud):
    _, item, _ = call(crud, "POST", body={"url": "https://example.com"})
    return item


