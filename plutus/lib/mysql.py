import datetime
import google.auth
import logging
import markus
import re
import sys

from plutus.lib.constants import APP
from pymysql.err import DatabaseError, Error, OperationalError
from googleapiclient import discovery
from google.protobuf.json_format import MessageToDict

log = logging.getLogger(f"{APP}.mysql")
metrics = markus.get_metrics(f"{APP}.mysql")


def upsert_budget(mysql_cursor, budget, project_id, config_type, alert_emails):
    """Upserts a row in the budgets mysql table."""

    budget_dict = MessageToDict(
        budget.__class__.pb(budget), preserving_proto_field_name=True
    )

    # Construct column values
    budget_id = budget_dict["name"]
    display_name = budget_dict["display_name"]

    # Currently Plutus only manages budgets for single projects.
    if (
        "projects" in budget_dict["budget_filter"]
        and len(budget_dict["budget_filter"]["projects"]) == 1
    ):
        project_number = budget_dict["budget_filter"]["projects"][0].replace(
            "projects/", ""
        )
    else:
        # This is a design decision based on the budgets API which only allows 0(ALL) or 1 project
        log.error(
            "Unexpected error. Plutus should only manage budgets for single projects."
        )
        metrics.incr(
            "error_count",
            tags=[
                "type:project_budget_filter",
                f"project_id:{project_id}",
                f"config_type:{config_type}",
            ],
        )
        sys.exit(1)

    if "services" in budget_dict["budget_filter"]:
        products = ",".join(budget_dict["budget_filter"]["services"])
    else:
        products = "ALL"

    owner_emails = get_owner_emails_for_project(project_id, alert_emails)

    if budget_dict["amount"].get("specified_amount") is None:
        budget_type = "LASTMONTH"
        budget_amount = "-1"
    else:
        budget_type = "AMT"
        budget_amount = budget_dict["amount"]["specified_amount"]["units"]

    if budget_dict["budget_filter"]["credit_types_treatment"] == "INCLUDE_ALL_CREDITS":
        include_credits = "TRUE"
    elif (
        budget_dict["budget_filter"]["credit_types_treatment"] == "EXCLUDE_ALL_CREDITS"
    ):
        include_credits = "FALSE"
    else:
        log.error(
            "Unexpected error. Credits_type_treatment should be either of \
                  INCLUDE_ALL_CREDITS or EXCLUDE_ALL_CREDITS."
        )
        log.error("Google may have changed their budgets API.")
        include_credits = "FALSE"
        metrics.incr(
            "error_count",
            tags=[
                "type:credits_type_treatment",
                f"project_id:{project_id}",
                f"config_type:{config_type}",
            ],
        )

    if budget_dict["notifications_rule"].get("pubsub_topic") is None:
        pubsub = "FALSE"
        pubsub_topic = "NA"
    else:
        pubsub = "TRUE"
        pubsub_topic = budget_dict["notifications_rule"]["pubsub_topic"]

    now = datetime.datetime.utcnow()
    curr_time = now.strftime("%Y-%m-%d %H:%M:%S")

    last_modified = curr_time
    created_date = curr_time

    sql = f""" INSERT INTO budgets (
budget_id,
display_name,
project_id,
project_number,
products,
budget_type,
budget_amount,
include_credits,
pubsub,
pubsub_topic,
owner_emails,
created_date,
last_modified,
config_type
)
VALUES
(
'{budget_id}',
'{display_name}',
'{project_id}',
'{project_number}',
'{products}',
'{budget_type}',
{budget_amount},
{include_credits},
{pubsub},
'{pubsub_topic}',
'{owner_emails}',
'{created_date}',
'{last_modified}',
'{config_type}'
)
ON DUPLICATE KEY UPDATE
display_name = '{display_name}',
project_id = '{project_id}',
project_number = '{project_number}',
products = '{products}',
budget_type = '{budget_type}',
budget_amount = {budget_amount},
include_credits = {include_credits},
pubsub = {pubsub},
pubsub_topic = '{pubsub_topic}',
owner_emails = '{owner_emails}',
last_modified = '{last_modified}',
config_type = '{config_type}'
"""

    try:
        mysql_cursor.execute(sql)
        metrics.incr(
            "upsert_count",
            tags=[f"project_id:{project_id}", f"config_type:{config_type}"],
        )
    except OperationalError as err:
        log.fatal(f"Operational error while running query: {sql}. Error: {err}")
        metrics.incr(
            "error_count",
            tags=[
                "type:sql_operational_err",
                f"project_id:{project_id}",
                f"config_type:{config_type}",
            ],
        )
    except DatabaseError as err:
        log.fatal(f"Database error while running query: {sql}. Error: {err}")
        metrics.incr(
            "error_count",
            tags=[
                "type:sql_db_err",
                f"project_id:{project_id}",
                f"config_type:{config_type}",
            ],
        )
    except Error as err:
        log.fatal(f"Exception while running query: {sql}. Error: {err}")
        metrics.incr(
            "error_count",
            tags=[
                "type:sql_exception",
                f"project_id:{project_id}",
                f"config_type:{config_type}",
            ],
        )


def get_owner_emails_for_project(
    project_id, alert_emails, default="dataops@mozilla.com"
):
    """Returns a string representation of the Union of:
    1. The @mozilla.com users(emails) with 'roles/owner' permission on the project id
    2. The list of alert_emails from yaml configuration
    or returns default otherwise.
    """

    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )

    service = discovery.build(
        "cloudresourcemanager", "v1", credentials=credentials, cache_discovery=False
    )

    pattern = re.compile("^user:(.*@mozilla.com)$")

    policy_request = service.projects().getIamPolicy(resource=project_id, body={})
    policy_response = policy_request.execute()
    metrics.incr(
        "gcp_api_request_count",
        tags=["type:resource_manager.getIamPolicy", f"project_id:{project_id}"],
    )

    members = set()
    if policy_response.get("bindings"):
        # Because the api is unreliable that this key will always exist
        for binding in policy_response["bindings"]:
            if binding["role"] == "roles/owner":
                for user in binding["members"]:
                    match = pattern.match(user)
                    if match:
                        members.add(match.group(1))

    # Add alert emails to the set
    members.update(alert_emails)

    if len(members) == 0:
        owner_emails = default
    else:
        owner_emails = ",".join(sorted(members))

    return owner_emails


def count_budgets(mysql_cursor):
    sql = f"SELECT COUNT(*) as cnt FROM budgets"
    try:
        mysql_cursor.execute(sql)
        budget_count = mysql_cursor.fetchone()[0]
        log.info(f"budget_count is {budget_count}")
        metrics.gauge("plutus.budget_count", value=int(budget_count))
    except OperationalError as err:
        log.fatal(f"Operational error while running query: {sql}. Error: {err}")
        metrics.incr("error_count", tags=["type:sql_operational_err"])
    except DatabaseError as err:
        log.fatal(f"Database error while running query: {sql}. Error: {err}")
        metrics.incr("error_count", tags=["type:sql_db_err"])
    except Error as err:
        log.fatal(f"Exception while running query: {sql}. Error: {err}")
        metrics.incr("error_count", tags=["type:sql_exception"])
