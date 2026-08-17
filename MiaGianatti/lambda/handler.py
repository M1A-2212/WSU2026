import json
import boto3
import CWPutData
import constants
import urllib

def lambda_handler(event, context):

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
