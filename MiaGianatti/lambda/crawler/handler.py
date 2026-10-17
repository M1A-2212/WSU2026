import json
import os
import time
import urllib.request

import boto3
from boto3.dynamodb.conditions import Attr

import CWPutData
import constants

OPS_NAMESPACE = "WebCrawler/Ops"
cw_client = boto3.client("cloudwatch")
targets_table = boto3.resource("dynamodb").Table(os.environ["TARGETS_TABLE"])


def lambda_handler(event, context):
    start = time.time()
    urls = get_urls()
    for url in urls:
        check_url(url)
    put_ops_metrics(time.time() - start, len(urls))
    return {"statusCode": 200, "body": json.dumps({"message": "Health Check Complete!"})}


def get_urls():
    urls, kwargs = [], {"FilterExpression": Attr("enabled").eq(True)}
    while True:
        r = targets_table.scan(**kwargs)
        urls += [i["url"] for i in r["Items"]]
        if "LastEvaluatedKey" not in r:
            return urls
        kwargs["ExclusiveStartKey"] = r["LastEvaluatedKey"]


def check_url(url):
    start = time.time()
    try:
        response = urllib.request.urlopen(url, timeout=5)
        availability = 1 if response.status == 200 else 0
        response_size = len(response.read())
    except Exception:
        availability = 0
        response_size = 0
    elapsed = time.time() - start

    CWPutData.putDataFunction(constants.NAMESPACE, constants.METRIC_AVAILABILITY, url, availability)
    CWPutData.putDataFunction(constants.NAMESPACE, constants.METRIC_LATENCY, url, elapsed)
    CWPutData.putDataFunction(constants.NAMESPACE, constants.METRIC_RESPONSE_SIZE, url, response_size)


def put_ops_metrics(run_seconds, urls_checked):
    cw_client.put_metric_data(
        Namespace=OPS_NAMESPACE,
        MetricData=[
            {"MetricName": "RunDurationSeconds", "Value": run_seconds, "Unit": "Seconds"},
            {"MetricName": "UrlsChecked", "Value": urls_checked, "Unit": "Count"},
        ],
    )