import boto3

def putDataFunction (namespace, metricName, url, value):
    return client.put_metric_data(
        Namespace = namespace,
        MetricData = [
            {
                'MetricName': metricName,
                'Dimensions': [
                    {
                        'Name': 'URL'
                        #'Value' 'URL'
                    },
                ],

                'Value': value
            }
        ]
    )