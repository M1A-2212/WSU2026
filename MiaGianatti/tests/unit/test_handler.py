# import json
# import boto3
# import pytest
 
 
# def sns_event(alarm="LATENCY Alarm", new="ALARM", old="OK", **extra):
#     message = {
#         "AlarmName": alarm,
#         "NewStateValue": new,
#         "OldStateValue": old,
#         **extra,
#     }
#     return {
#         "Records": [{"EventSource": "aws:sns", "Sns": {"Message": json.dumps(message)}}]
#     }
 
 
# class FakeResponse:
#     def __init__(self, status=200, body=b"x" * 6000):
#         self.status = status
#         self._body = body
 
#     def read(self):
#         return self._body
 
 
# def fake_response(status=200, body=b"x" * 6000):
#     return FakeResponse(status, body)
 
 
# def metrics_sent(cwput):
#     return {args[1]: args[3] for args in cwput.calls}


# def test_put_ops_metrics_publishes_to_ops_namespace(self, crawler):
#         crawler.put_ops_metrics(12.5, 3)
 
#         listed = boto3.client("cloudwatch").list_metrics(Namespace="WebCrawler/Ops")
#         assert {m["MetricName"] for m in listed["Metrics"]} == {
#             "RunDurationSeconds",
#             "UrlsChecked",
#         }
 
 
# class TestHealthCheck:
#     def test_checks_every_enabled_url_and_reports_ops_metrics(
#         self, crawler, targets_table, monkeypatch
#     ):
#         targets_table.put_item(Item={"id": "1", "url": "https://a.com", "enabled": True})
#         targets_table.put_item(Item={"id": "2", "url": "https://b.com", "enabled": True})
#         targets_table.put_item(Item={"id": "3", "url": "https://off.com", "enabled": False})
 
#         checked = []
#         ops_calls = []
        
#         monkeypatch.setattr(crawler, "check_url", checked.append, raising=False)
#         monkeypatch.setattr(
#             crawler, "put_ops_metrics", lambda secs, n: ops_calls.append((secs, n))
#         )
 
#         result = crawler.lambda_handler({}, None)
 
#         assert sorted(checked) == ["https://a.com", "https://b.com"]
#         assert len(ops_calls) == 1
#         run_seconds, urls_checked = ops_calls[0]
#         assert urls_checked == 2
#         assert run_seconds >= 0
#         assert result["statusCode"] == 200
#         assert json.loads(result["body"]) == {"message": "Health Check Complete!"}