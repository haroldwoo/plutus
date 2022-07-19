from plutus.lib.constants import (
    APP,
    PLUTUS_CONFIG_TYPE_PROJECT,
    PLUTUS_CONFIG_TYPE_PARENT,
    PLUTUS_CONFIG_TYPE_LABEL,
    PLUTUS_CONFIG_TYPE_DEFAULT,
)
import logging
import markus
import sys

metrics = markus.get_metrics(f"{APP}.projectbudget")


class ProjectBudget:
    """
    ProjectBudget class for representing a configuration object

    Fields:
    -------
    project_id - str - GCP project id
    budget_type - str - "AMT or LASTMONTH"
    budget_amount - int - Though googles rpc will use google.type.money_pb2.money - monthly budget amount in USD
    products - list(str) - currently only ['ALL'] supported
    alert_emails - list(str) - emails to alert when budget thresholds hit
    threshold_rules - list(object) - objects have threshold_percent and spend_basis fields
    include_credits - bool - Include GCP credits in the budget calculations
    pubsub - bool - Send budget alerts to pubsub? Required for pagerduty/slack
    pubsub_topic - str - Optional. Will default to default_pubsub_topic
    alert_slack_channel_id - str - Optional. Will send notifications to this channel plus the default plutus channel.

    billing_account_id - str - GCP billing account id
    display_name - budget display name
    config_type - str - The type of budget. Either project, parent, label, or default
    parent_id - str - Optional - GCP parent folder id. For use with config_type parent
    label_list - str - Optional - list of label k/v pairs. For use with config_type label

    """

    def __init__(
        self, project_dict, config_type, billing_account_id, default_pubsub_topic
    ):
        self.logger = logging.getLogger(f"{APP}.projectbudget")

        for key in project_dict:
            setattr(self, key, project_dict[key])

        self.billing_account_id = billing_account_id

        if "pubsub_topic" not in project_dict:
            self.pubsub_topic = default_pubsub_topic

        if "alert_slack_channel_id" not in project_dict:
            self.alert_slack_channel_id = None

        self.config_type = config_type
        if config_type == PLUTUS_CONFIG_TYPE_PROJECT:
            self.display_name = f"plutus-{self.project_id}"
        elif config_type == PLUTUS_CONFIG_TYPE_PARENT:
            self.parent_id = project_dict["parent_folder_id"]
            self.display_name = f"plutus-{self.parent_id}-{self.project_id}"
        elif config_type == PLUTUS_CONFIG_TYPE_LABEL:
            self.display_name = f"plutus-labels-{self.project_id}"
            self.label_list = project_dict["label_list"]
        elif config_type == PLUTUS_CONFIG_TYPE_DEFAULT:
            self.display_name = f"plutus-default-{self.project_id}"
        else:
            self.logger.error(f"Error. Unknown plutus config type found: {config_type}")
            metrics.incr(
                "error_count",
                tags=[
                    "type:misconfig",
                    f"project_id:{self.project_id}",
                    f"config_type:{config_type}",
                ],
            )
            sys.exit(1)

    def __str__(self):
        return f"""{self.project_id}, {self.budget_type}, {self.budget_amount},
{self.products}, {self.alert_emails}, {self.threshold_rules},
{self.include_credits}, {self.pubsub}, {self.pubsub_topic}, {self.display_name}"""
