import json
import boto3
import CWPutData as cw

def lambda_handler(event, context):
    client = boto3.client('cloudwatch')

    response = cw.CWPutData(constants.namespace, constants.metricAvailability, constants.metricLatency)

    #This is used to make sure everything works
    return{
        "statusCode": 200,
        "body": json.dumps({"message": "Hello World!"})        
    }
