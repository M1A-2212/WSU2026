# WebHealthStack
An AWS CDK (Python) project that monitors the health of websites. A scheduled Lambda "crawler" checks a list of target URLs every 5 minutes and publishes availability, latency and response-size metrics to CloudWatch. Alarms notify you by email, log every state change to DynamoDB, and, for problems with the crawler itself, automatically roll the crawler back to its previous version. A small REST API lets you add, edit and remove the URLs being monitored.

## What is Deployed?
* An IAM User role with full CloudWatch access
* Lambda function
* EventBridge Rule, which triggers the Lambda function at a fixed rate
* CloudWatch metrics and alarms for the website
    * Latency
    * Availability
    * Response size
* Notifications for the alarms for a subscription list
* A DynamoDB NoSQL database that logs the alarms that have been triggered
* CloudWatch Dashboard with a 7-day interval
* The function has a hard-coded `DESTROY` command written in to delete the stack when it is
  destroyed, not retained

## Technologies Used
- AWS CDK
- AWS Lambda
- AWS S3
- Amazon CloudWatch
- Amazon DynamoDB
- Amazon Eventbridge
- Amazon API Gateway
- Amazon SNS
- GitHub
- Python

## Project Structure
```
project/
  app.py                     CDK app entry point
  webHealthStack.py          The WebHealthStack
  pipeLineStack.py           Stack for the code pipeline
  pipelineStage.py           Assists in deploying pipeline for WebHealthStack
  constants.py               Monitored URL, metric namespace and metric names (used by the stack)
  lambda/
    crawler/
      handler.py             Crawler: reads targets, checks URLs, publishes metrics
      CWPutData.py           Helper that publishes a metric to CloudWatch
      constants.py           Copy of the root constants.py (see note below)
    alarm_logger/
      handler.py             Writes alarm state changes from SNS to DynamoDB
    crud/
      handler.py             CRUD for targets + metrics endpoints
  tests/                     Unit, functional and integration tests (pytest)
```

## Components

### Crawler Lambda (`lambda/crawler`)
- Runtime Python 3.12, 30 s timeout, 256 MB, Lambda Insights enabled.
- A URL counts as **available (1)** only when the response status is exactly `200`. Any other status, timeout or network error is **unavailable (0)** with a response size of 0. Redirects are followed.
- Publishes per URL, in the namespace `NAMESPACE` with a `URL` dimension: `AVAILABILITY`, `LATENCY` (seconds), `RESPONSE_SIZE` (bytes).
- Publishes per run, in `WebCrawler/Ops`: `RunDurationSeconds` and `UrlsChecked`.
- Environment: `TARGETS_TABLE`.

### Alarm logger Lambda (`lambda/alarm_logger`)
Subscribed to the *Alarm Notifications* topic. For each SNS record it writes an item to the alarm table: `pk` (alarm name), `timestamp` (UTC ISO 8601), `new_state`, `old_state`, `reason`, `region`, `account_id`. Environment: `ALARM_NOTIFICATIONS_TABLE`.
 
### CRUD Lambda (`lambda/crud`)
Handles the REST API. Validates that `url` is an `http` or `https` URL with a host. Environment: `TARGETS_TABLE`.
 
# Rollback Lambda (inline code in `webHealthStack.py`)
Subscribed to the *Rollback Notifications* topic. On an `ALARM` state it reads the version the alias currently points at, finds the highest published version below it, and points the alias there. `OK` and `INSUFFICIENT_DATA` notifications are ignored. If there is no earlier version, nothing changes. Replaces CodeDeploy, which is not available in this account.


## Setup
This project is set up like a standard Python project. The initialization
process also creates a virtualenv within this project, stored under the `.venv`
directory.  To create the virtualenv it assumes that there is a `python3`
(or `python` for Windows) executable in your path with access to the `venv`
package. If for any reason the automatic creation of the virtualenv fails,
you can create the virtualenv manually.
Node.js is also required for the AWS CDK CLI.

To install the AWS CDK CLI
``` bash
$ npm install -g aws-cdk
```

To set up the target account and region
```bash
$ cdk bootstrap
```

To set up the AWS CDK
```bash
$ pip install aws-cdk-lib constructs
```

## Configuration
 
Edit these before deploying:
 
-Monitored URL(s): `URL` in `constants.py` (and the copy in `lambda/crawler/constants.py`). Alarms and dashboard widgets in the stack are created for the URLs in the `urls` list in `webHealthStack.py`. Targets added through the API are crawled and produce metrics, but only URLs listed in the stack get alarms and dashboard widgets.
-Alert email: the `EmailSubscription` address in `webHealthStack.py`. The recipient must confirm the subscription email from AWS.
-Thresholds: the `alarm_config` dictionary, `CRAWLER_TIMEOUT_SECONDS` and `CRAWLER_MEMORY_MB` in `webHealthStack.py`.


## Deploying
 
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
 
cdk synth
cdk deploy WebHealthStack
```

To add additional dependencies, for example other CDK libraries, just add
them to your `requirements.txt` or `requirements-dev.txt` file and rerun the `python -m pip install -r requirements.txt`
command.


## Useful commands

 * `cdk ls`          list all stacks in the app
 * `cdk bootstrap`   deploys a CDK toolkit 
 * `cdk synth`       emits the synthesized CloudFormation template
 * `cdk deploy`      deploy this stack to your default AWS account region
 * `cdk diff`        compare deployed stack with current state
 * `cdk docs`        open CDK documentation


 The CDK deploys the stack configured in your AWS CLI profile, or the default us-east-1.
 Make sure to change the region if that is not where you plan to deploy it.


## Monitoring
Once the stack is deployed, login to your AWS management console and use the CloudWatch service
to view the dashboard that records the metrics and alarms.
The alarms that are triggered will send out email notfications, and the alarms will also
be logged in the DynamoDB service for records.

## API Functions
Add
```bash
curl -X POST https://fb263s0um4.execute-api.us-east-1.amazonaws.com/prod/targets \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-site.com"}'m
```

Delet
```bash
curl -X DELETE https://<api-id>.execute-api.us-east-1.amazonaws.com/prod/targets/<id>
```
Read
```bash
curl https://<api-id>.execute-api.us-east-1.amazonaws.com/prod/targets
```

Update
```bash
curl -X PUT https://<api-id>.execute-api.us-east-1.amazonaws.com/prod/targets/<id> \
  -H "Content-Type: application/json" \
  -d '{"url": "https://new-site.com", "enabled": true}'
```

## Testing
```bash
$ pytest/tests/unit
$ pytest/tests/function
```
Integration tests can only be tested properly when the Pipeline is deployed.
If pytest is used for these tests, they will be skipped

## Clean-Up
Use `cdk destroy` to remove the stack and stop all processes. There is a hard-coded command
but this ensures that all resources are destroyed regardless.

