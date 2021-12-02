import base64
import boto3
import json
import pymysql
import pypd
import os
import re
import slack

from botocore.exceptions import ClientError
from datetime import datetime, timedelta

# See https://api.slack.com/docs/token-types#bot for more info
BOT_ACCESS_TOKEN = os.environ["OAUTH_TOKEN"]

CHANNEL_ID = os.environ["CHANNEL_ID"]

MYSQL_HOST = os.environ["MYSQL_HOST"]
MYSQL_USER = os.environ["MYSQL_USER"]
MYSQL_PASS = os.environ["MYSQL_PASS"]
MYSQL_DB = os.environ["MYSQL_DB"]

SMTP_EMAIL = os.environ["SMTP_EMAIL"]
ACCESS_KEY = os.environ["AWS_ACCESS_KEY_ID"]
SECRET_KEY = os.environ["AWS_SECRET_ACCESS_KEY"]

PAGERDUTY_KEY = os.environ["PAGERDUTY_KEY"]

slack_client = slack.WebClient(token=BOT_ACCESS_TOKEN)

mysql_conn = pymysql.connect(
    host=MYSQL_HOST, user=MYSQL_USER, password=MYSQL_PASS, db=MYSQL_DB, autocommit=True
)


def send_alert(budget_id):
    """Determine whether to send an alert or not based on last alert time."""

    with mysql_conn.cursor() as cursor:
        sql = "SELECT `last_alert` FROM `alerts` WHERE `budget_id`=%s"
        cursor.execute(sql, [budget_id])
        result = cursor.fetchone()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if result is None:
            # No record found, insert new row into table
            sql = "INSERT INTO `alerts` (`budget_id`, `last_alert`) VALUES (%s, %s)"
            cursor.execute(sql, (budget_id, now))
            return True
        else:
            # Record found, check timestamp of last alert time
            past = datetime.now() - timedelta(days=1)

            # Untuple the sql result. This will return a datetime.datetime object.
            last_alert_time = result[0]

            if last_alert_time < past:
                # If last alerted over a day ago, update table and send alert
                sql = "UPDATE `alerts` set `last_alert`=%s WHERE `budget_id`=%s"
                cursor.execute(sql, (now, budget_id))
                return True
            else:
                return False


def get_emails_for_budget(budget_id):
    with mysql_conn.cursor() as cursor:
        sql = "SELECT `owner_emails` FROM `budgets` WHERE `budget_id`=%s"
        cursor.execute(sql, [budget_id])
        result = cursor.fetchone()
        if result is None:
            emails = None
        else:
            # result should be a tuple
            emails = "".join(result)
        return emails


def send_email(emails, message, project_id=None):
    subject = "Plutus - GCP Budget alert"
    if project_id is not None:
        subject += f" - {project_id}"
    charset = "UTF-8"
    client = boto3.client(
        "ses",
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name="us-west-2",
    )

    try:
        response = client.send_email(
            Destination={
                "ToAddresses": emails,
            },
            Message={
                "Body": {
                    "Text": {
                        "Charset": charset,
                        "Data": message,
                    },
                },
                "Subject": {
                    "Charset": charset,
                    "Data": subject,
                },
            },
            Source=SMTP_EMAIL,
        )
    except ClientError as e:
        print(e.response["Error"]["Message"])
    else:
        print(f"Email sent! Message ID: {response['MessageId']}")


def send_pagerduty_alert(message, budget_id):
    pypd.api_key = PAGERDUTY_KEY

    # create a version 2 event
    pypd.EventV2.create(
        data={
            "routing_key": PAGERDUTY_KEY,
            "event_action": "trigger",
            "dedup_key": budget_id,
            "payload": {
                "summary": message,
                "severity": "error",
                "source": "plutus-budget-monitor(cloud function)",
            },
        }
    )


def post_to_channel(message):
    slack_client.chat_postMessage(channel=CHANNEL_ID, text=message)


def decode_budget_data(data):
    data = base64.b64decode(data)
    return json.loads(data)


def budget_notify(notification_attrs, notification_data):

    billing_account_id = notification_attrs["billingAccountId"]
    budget_id = notification_attrs["budgetId"]
    budget_name = notification_data["budgetDisplayName"]
    cost_amount = notification_data["costAmount"]
    budget_amount = notification_data["budgetAmount"]

    if notification_data.get("alertThresholdExceeded"):
        # From google documentation, key exists only if a threshold was exceeded
        alert_threshold_exceeded = notification_data.get("alertThresholdExceeded")

        pattern = re.compile("^plutus-(labels|\d*-)*(.*)$")  # noqa: W605
        match = pattern.match(budget_name)

        message = ""
        project_id = None
        if match:
            project_id = match.group(2)
            message += f"Budget exceeded for project: {project_id}. "

        message += f"budget_name: {budget_name}\
        budget_id: {budget_id},\
        budget_amount: {budget_amount},\
        cost_amount: {cost_amount},\
        alert_threshold_exceeded: {alert_threshold_exceeded}"

        send_pagerduty_alert(message, budget_id)

        full_budget_id = f"billingAccounts/{billing_account_id}/budgets/{budget_id}"

        if send_alert(full_budget_id):
            # Send slack alert
            post_to_channel(message)

            # Send email alert
            emails = get_emails_for_budget(full_budget_id)
            if emails is not None:
                send_email(emails.split(","), message, project_id)
            else:
                post_to_channel(
                    f"Send email failed. Budget id {full_budget_id} not found in db."
                )


# Entrypoint of GCP Cloud Function
def process_pubsub(data, context):
    notification_attrs = data["attributes"]
    notification_data = decode_budget_data(data["data"])

    try:
        budget_notify(notification_attrs, notification_data)
    except Exception as err:
        post_to_channel(f"Plutus budget notify failed: {err}")
        post_to_channel(f"{notification_attrs} - {notification_data}")
        raise
