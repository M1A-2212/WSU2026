
# WebHealthStack
This is an AWS CDK stack run in Python that will perform health checks of "https://library.westernsydney.edu.au/". This uses a Lambda function to publish the CloudWatch metrics and alarms on a dashboard.

## What is Deployed?
* An IAM User role with full CloudWatch access
* Lambda function
* EventBridge Rule, which triggers the Lambda function at a fixed rate
* CloudWatch metrics and alarms for the website
    * Latency
    * Availability
    * Response size
* CloudWatch Dashboard with a 7-day interval
* The function has a hard-coded `DESTROY` command written in to delete the stack when it is
  destroyed, not retained



# Setup

This project is set up like a standard Python project.  The initialization
process also creates a virtualenv within this project, stored under the `.venv`
directory.  To create the virtualenv it assumes that there is a `python3`
(or `python` for Windows) executable in your path with access to the `venv`
package. If for any reason the automatic creation of the virtualenv fails,
you can create the virtualenv manually.

To manually create a virtualenv on MacOS and Linux:
```
$ python3 -m venv .venv
```

After the init process completes and the virtualenv is created, you can use the following
step to activate your virtualenv.
```
$ source .venv/bin/activate
```
If you are a Windows platform, you would activate the virtualenv like this:
```
% .venv\Scripts\activate.bat
```

Once the virtualenv is activated, you can install the required dependencies.
```
$ pip install -r requirements.txt
```

To add additional dependencies, for example other CDK libraries, just add
them to your `requirements.txt` file and rerun the `python -m pip install -r requirements.txt`
command.



## Useful commands

 * `cdk ls`          list all stacks in the app
 * `cdk bootstrap`   deploys a CDK toolkit 
 * `cdk synth`       emits the synthesized CloudFormation template
 * `cdk deploy`      deploy this stack to your default AWS account/region
 * `cdk diff`        compare deployed stack with current state
 * `cdk docs`        open CDK documentation


 The CDK deploys the stack configured in your AWS CLI profile, or the default us-east-1.
 Make sure to change the region if that is not where you plan to deploy it.

# Monitoring
Once the stack is deployed, login to your AWS management console and use the CloudWatch service
to view the dashboard that records the metrics and alarms.


# Clean-Up
Use `cdk destroy` to remove the stack and stop all processes. There is a hard-coded command
but this ensures that all resources are destroyed regardless.

Enjoy!
