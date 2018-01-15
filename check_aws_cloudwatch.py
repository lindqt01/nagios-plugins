#!/usr/bin/python
#
# Author: Tobias Lindqvist 2017-11-27
#
# 2017-12-28: Simplified logic. /Tobias Lindqvist

import boto3
import botocore.session
import argparse
from datetime import datetime, timedelta
from operator import itemgetter
import re
import signal

E_OK=0
E_WARN=1
E_CRIT=2
E_UNKNOWN=3
TIMEOUT=15

def handler(signum, frame):
    raise Exception("op5 timed out when trying to contact AWS")

parser = argparse.ArgumentParser()
parser.add_argument("region", help="AWS region")
parser.add_argument("profile", help="AWS region profile")
parser.add_argument("metric", help="AWS metric")
parser.add_argument("namespace", help="AWS namespace")
parser.add_argument("dimensions", help="AWS dimensions")
parser.add_argument("warning", help="Warning threshold", type=int)
parser.add_argument("critical", help="Critical threshold", type=int)
parser.add_argument("operator", help="lt (less than) or gt (greater than)")
parser.add_argument("period", help="minutes back in time", type=int)
args = parser.parse_args()

# Convert minutes to seconds
period_seconds = args.period * 60

# Parse command line argument
match = re.search(r'Name=(.*),Value=(.*)', args.dimensions)
name = match.group(1)
value = match.group(2)


# Set timeout
signal.signal(signal.SIGALRM, handler)
signal.alarm(TIMEOUT)

try:
    # Set profile and create a cloudwatch client in region specified
    boto3.setup_default_session(profile_name=args.profile)
    cloudwatch = boto3.client('cloudwatch', region_name=args.region)

    response = cloudwatch.get_metric_statistics(
        Namespace=args.namespace,
        Dimensions=[ { "Name": name, "Value": value } ],
        MetricName=args.metric,
        StartTime=datetime.utcnow() - timedelta(seconds=period_seconds),
        EndTime=datetime.utcnow(),
        Period=period_seconds,
        Statistics=[
            'Average'
        ]
    )
    if not response['Datapoints']:
        print("UNKNOWN - No value received from Cloudwatch")
        quit(E_UNKNOWN)
except Exception, exc:
    print exc
    quit(E_UNKNOWN)


# Extract metric value
datapoints = response['Datapoints']
last_datapoint = sorted(datapoints, key=itemgetter('Timestamp'))[-1]
metric_value = last_datapoint['Average']

# Compose message
message = "Average %s last %d minutes is %f | %s=%f;%d;%d" % (args.metric, args.period, metric_value, args.metric, metric_value, args.warning, args.critical)

# Check against thresholds
if args.operator == 'lt':
    if metric_value < args.critical:
        print("CRITICAL - %s") % message
        quit(E_CRIT)
    elif metric_value < args.warning:
        print("WARNING - %s") % message
        quit(E_WARN)
    else:
        print("OK - %s") % message
        quit(E_OK)
elif args.operator == 'gt':
    if metric_value > args.critical:
        print("CRITICAL - %s") % message
        quit(E_CRIT)
    elif metric_value > args.warning:
        print("WARNING - %s") % message
        quit(E_WARN)
    else:
        print("OK - %s") % message
        quit(E_OK)
