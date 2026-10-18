import json

import pytest

from tests.helpers import api_event


def call(crud, method, target_id=None, body=None, raw_body=None):
    r = crud.lambda_handler(api_event(method, target_id, body, raw_body), None)
    return r["statusCode"], (json.loads(r["body"]) if r["body"] else None), r


def create(crud, url="https://example.com", **extra):
    status, body, _ = call(crud, "POST", body={"url": url, **extra})
    assert status == 201
    return body

def test_full_lifecycle(crud):
    created = create(crud, "https://a.example.com")
    tid = created["id"]

    assert call(crud, "GET")[1] == [created]
    assert call(crud, "GET", tid)[1] == created

    status, updated, _ = call(crud, "PUT", tid, {"url": "https://b.example.com", "enabled": False})
    assert status == 200
    assert updated["url"] == "https://b.example.com" and updated["enabled"] is False
    assert updated["created_at"] == created["created_at"]
    assert updated["updated_at"] >= created["updated_at"]

    assert call(crud, "DELETE", tid)[0] == 204
    assert call(crud, "GET", tid)[0] == 404
    assert call(crud, "GET")[1] == []