import json
import boto3
import CWPutData
import constants

def lambda_handler(event, context):
    client = boto3.client('cloudwatch')

    response = CWPutData.putDataFunction(constants.NAMESPACE, constants.METRIC_AVAILABILITY, constants.METRIC_LATENCY, constants.RESPONSE_SIZE)

    #This is used to make sure everything works
    return{
        "statusCode": 200,
        "body": json.dumps({"message": "Health Check Complete!"})        
    }
