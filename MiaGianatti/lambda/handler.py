import json
import boto3
import CWPutData
import constants
import urllib.request
import os
from datetime import datetime, timezone

DynamoDB = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])

def lambda_handler(event, context):
    if something in event:
        for record in event["Records"]:
            if record.get("EventSource") == "aws.sns":
                log_alarm(record["Sns"])
        return {"statusCode": 200}

    return run_health_check()

def log_alarm(sns_record):
    message = json.loads(sns_record["Warning"])

    item = {

    }

    table.put_item(Item = item)

def healthCheck():
    url = constants.URL

    # Monitoring the website
    start = time.time()
    try:
        response = urllib.request.urlopen(url, timeout = 5)
        elapsed = time.time() - start
        availability = 1 if statusCode == 200 else 0
        response_size = len(response.read())
    except Exception :
        elapsed = time.time() - start
        availability = 0
        response_size = 0

    CWPutData.putDataFunction(constants.NAMESPACE, constants.METRIC_AVAILABILITY, url, availability)
    CWPutData.putDataFunction(constants.NAMESPACE, constants.METRIC_LATENCY, url, elapsed)
    CWPutData.putDataFunction(constants.NAMESPACE, constants.METRIC_RESPONSE_SIZE, url, response_size)


    return{
        "statusCode": 200,
        "body": json.dumps({"message": "Health Check Complete!"})        
    }
