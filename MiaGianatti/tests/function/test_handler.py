import json
import uuid

def add_target(table, url, enabled=True):
    table.put_item(Item={"id": str(uuid.uuid4()), "url": url, "enabled": enabled})


def test_healthy_site_publishes_all_three_metrics(crawler, targets_table, site, read_metric):
    add_target(targets_table, f"{site}/ok")
    result = crawler.lambda_handler({}, None)

    ns, url = crawler.constants.NAMESPACE, f"{site}/ok"
    assert result["statusCode"] == 200
    assert read_metric(ns, "AVAILABILITY", url) == 1
    assert read_metric(ns, "RESPONSE_SIZE", url) == 6000
    assert 0 <= read_metric(ns, "LATENCY", url) < 5
    
def test_one_failure_does_not_stop_other_targets(crawler, targets_table, site, read_metric):
    add_target(targets_table, f"{site}/missing")
    add_target(targets_table, f"{site}/ok")
    crawler.lambda_handler({}, None)
    ns = crawler.constants.NAMESPACE
    assert read_metric(ns, "AVAILABILITY", f"{site}/missing") == 0
    assert read_metric(ns, "AVAILABILITY", f"{site}/ok") == 1


def test_many_targets_are_all_checked(crawler, targets_table, site, read_metric):
    for i in range(30):
        add_target(targets_table, f"{site}/ok?n={i}")
    crawler.lambda_handler({}, None)
    assert read_metric("WebCrawler/Ops", "UrlsChecked") == 30