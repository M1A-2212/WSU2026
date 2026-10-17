import boto3
import constants

client = boto3.client('cloudwatch')

def putDataFunction (namespace, metricName, url, value):
    return client.put_metric_data(
        Namespace = namespace,
        MetricData = [
            {
                'MetricName': metricName,
                'Dimensions': [
                    {
                        'Name': 'URL',
                        'Value': url
                    },
                ],

                'Value': value
            }
        ]
    )