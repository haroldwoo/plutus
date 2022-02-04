from plutus.lib.constants import APP
import copy
import logging
import markus

from google.protobuf.json_format import MessageToDict

import json
import sys
from google.api_core.exceptions import GoogleAPICallError, RetryError


metrics = markus.get_metrics(APP + ".gcphelper")


class GcpHelper:
    """
    Uses GCP billing budget and resource manager clients to get, update, and create budgets
    """

    def __init__(self, billing_client, resource_manager_client):
        self.billing_client = billing_client
        self.resource_manager_client = resource_manager_client
        self.logger = logging.getLogger(APP + ".gcphelper")

    def get_project_number(self, project_id):
        """Given a GCP project id, return the associated GCP project number."""
        # Ensure that the configured project_id actually exists in GCP
        try:
            project_object = self.resource_manager_client.fetch_project(project_id)
            metrics.incr(
                "gcp_api_request_count",
                tags=["type:resource_manager.fetch", f"project_id:{project_id}"],
            )
            project_number = project_object.number
            return project_number
        except Exception as err:
            self.logger.error(
                f"Error fetching project {project_id}: {err}. Double check config."
            )
            metrics.incr(
                "error_count",
                tags=["type:fetch_project_id_err", f"project_id:{project_id}"],
            )
            sys.exit(1)

        return None

    def get_budgets_by_project(self, project, project_number):
        """
        Retreives all budgets by project id & number. The Budgets API currently doesnt support this.
        Furthermore, when creating budgets via API, project ids are converted to project number,
        so we needed to pass in project number from the resourcemanager API also
        """
        budgets = []
        try:
            parent = self.billing_client.common_billing_account_path(
                project.billing_account_id
            )
            for budget in self.billing_client.list_budgets(parent=parent):
                if (
                    f"projects/{project.project_id}" in budget.budget_filter.projects
                    or f"projects/{project_number}" in budget.budget_filter.projects
                ):
                    budgets.append(budget)

            metrics.incr(
                "gcp_api_request_count",
                tags=["type:billing.list", f"project_id:{project.project_id}"],
            )
        except Exception as err:
            self.logger.error(
                f"Error listing budgets for {project.billing_account_id}: {err}."
            )
            metrics.incr(
                "error_count",
                tags=["type:billing.list_budgets", f"project_id:{project.project_id}"],
            )
            sys.exit(1)

        return budgets

    def has_existing_project_budget(self, project):
        """
        Given a project object, returns budget id if a plutus project specific budget
        already exists. None otherwise.

        """

        project_number = self.get_project_number(project.project_id)
        all_budgets = self.get_budgets_by_project(project, project_number)

        for budget in all_budgets:
            if budget.display_name == f"plutus-{project.project_id}":
                # Return budget id e.g. billingAccounts/{billingAccountId}/budgets/{budgetId}
                return budget.name

        return None

    def has_existing_parent_budget(self, parent_id, project):
        """
        Given a parent id and project object, returns budget id if a plutus parent budget
        already exists. None otherwise.

        """

        project_number = self.get_project_number(project.project_id)
        all_budgets = self.get_budgets_by_project(project, project_number)

        for budget in all_budgets:
            if budget.display_name == f"plutus-{parent_id}-{project.project_id}":
                return budget.name

        return None

    def has_existing_labels_budget(self, project):
        """
        Given a project object, returns budget id  if a plutus labels budget
        already exists. None otherwise.

        """

        project_number = self.get_project_number(project.project_id)
        all_budgets = self.get_budgets_by_project(project, project_number)

        for budget in all_budgets:
            if budget.display_name == f"plutus-labels-{project.project_id}":
                return budget.name

        return None

    def sync_config_with_gcp_budget(self, project, budget_dict, project_number):
        """
        Takes as a parameter a budget_dict which is a dict representation of a gcp proto budget
        and a project which is a projectBudget object created from yaml config.

        Returns two values.
        1. Boolean whether configuration and gcp budget match.
        2. A changed_budget object, with any diffs between config and GCP. Returns None if error.
        """

        ret_val = True
        # Make a deep copy, so tests can compare dicts more easily for changes
        changed_budget = copy.deepcopy(budget_dict)

        # Compare project id and project number to ensure we're dealing with the same budget.
        if (
            f"projects/{project.project_id}"
            not in budget_dict["budget_filter"]["projects"]
            and f"projects/{project_number}"
            not in budget_dict["budget_filter"]["projects"]
        ):
            self.logger.error("Project id/num not found, shouldn't happen...")
            metrics.incr(
                "error_count",
                tags=["type:misconfig", f"project_id:{project.project_id}"],
            )
            return False, None

        # Ensure the budget is only for a singular project. Plutus budgets manage single project
        if len(budget_dict["budget_filter"]["projects"]) != 1:
            self.logger.error("project ids list length != 1, shouldnt happen...")
            metrics.incr("error_count", tags=["type:multiple_projectids"])
            return False, None

        # Compare and update budget
        if project.budget_type == "AMT":
            if budget_dict["amount"].get("specified_amount") is None:
                self.logger.info("Change detected from LASTMONTH to AMT")
                ret_val = False

                changed_budget["amount"] = {
                    "specified_amount": {
                        "currency_code": "USD",
                        "units": project.budget_amount,
                    }
                }

            elif budget_dict["amount"]["specified_amount"]["currency_code"] != "USD":
                self.logger.error("non USD. This shouldnt happen.")
                metrics.incr(
                    "error_count",
                    tags=["type:non_usd", f"project_id:{project.project_id}"],
                )
                return False, None

            # Google rpcs changed units to string, and back to int again
            # When we call MessageToDict on a proto budget, the units are represented
            # as a string. But when we want to call the API later, it expects int.
            # We will cast both to str for comparison, in case google changes this again
            elif str(budget_dict["amount"]["specified_amount"]["units"]) != str(
                project.budget_amount
            ):
                self.logger.info("Change detected in budget units amount")
                ret_val = False
                changed_budget["amount"]["specified_amount"][
                    "units"
                ] = project.budget_amount

        elif project.budget_type == "LASTMONTH":
            if budget_dict["amount"].get("last_period_amount") is None:
                self.logger.info("Change detected from AMT to LASTMONTH")
                ret_val = False
                changed_budget["amount"] = {"last_period_amount": {}}
        else:
            self.logger.error("budget_type needs to be set to either: AMT or LASTMONTH")
            metrics.incr(
                "error_count",
                tags=["type:misconfig", f"project_id:{project.project_id}"],
            )
            return False, None

        # Compare and update include_credits
        if project.include_credits:
            if (
                budget_dict["budget_filter"]["credit_types_treatment"]
                != "INCLUDE_ALL_CREDITS"
            ):
                self.logger.info(
                    "Change in include_credits. Config=True, GCP=False, updating..."
                )
                ret_val = False
                changed_budget["budget_filter"][
                    "credit_types_treatment"
                ] = "INCLUDE_ALL_CREDITS"
        elif project.include_credits is False:
            if (
                budget_dict["budget_filter"]["credit_types_treatment"]
                != "EXCLUDE_ALL_CREDITS"
            ):
                self.logger.info(
                    "Change in include_credits. Config=False, GCP=True, updating..."
                )
                ret_val = False
                changed_budget["budget_filter"][
                    "credit_types_treatment"
                ] = "EXCLUDE_ALL_CREDITS"

        # Compare and update threshold_rules
        config_thresholds = project.threshold_rules
        budget_thresholds = budget_dict["threshold_rules"]
        pairs = zip(config_thresholds, budget_thresholds)
        if any(x != y for x, y in pairs) or len(config_thresholds) != len(
            budget_thresholds
        ):
            self.logger.info("Change detected in threshold_rules")
            ret_val = False
            changed_budget["threshold_rules"] = config_thresholds

        pubsub_topic = project.pubsub_topic

        # Compare and update pubsub
        if project.pubsub:
            if budget_dict.get("notifications_rule"):
                # GCP has changed the API object recently so that this key doesn't always exist.
                if (
                    budget_dict["notifications_rule"].get("pubsub_topic") is None
                    or budget_dict["notifications_rule"].get("schema_version") is None
                ):
                    self.logger.info(
                        "Pubsub changed to True in config but not setup in GCP."
                    )
                    ret_val = False

                    changed_budget["notifications_rule"] = {
                        "pubsub_topic": pubsub_topic,
                        "schema_version": "1.0",
                    }
                elif (
                    budget_dict["notifications_rule"].get("pubsub_topic")
                    == pubsub_topic
                    and budget_dict["notifications_rule"].get("schema_version") == "1.0"
                ):
                    # Pubsub matches config
                    pass
                else:
                    # Pubsub topic has changed
                    ret_val = False
                    changed_budget["notifications_rule"] = {
                        "pubsub_topic": pubsub_topic,
                        "schema_version": "1.0",
                    }
            else:
                # Configured pubsub to true but the notifications_rule key in GCP doesn't exist.
                ret_val = False
                changed_budget["notifications_rule"] = {
                    "pubsub_topic": pubsub_topic,
                    "schema_version": "1.0",
                }

        elif project.pubsub is False:
            if budget_dict.get("notifications_rule"):
                # GCP has changed the API object recently so that this key doesn't always exist.
                if (
                    budget_dict["notifications_rule"].get("pubsub_topic") is not None
                    or budget_dict["notifications_rule"].get("schema_version")
                    is not None
                ):
                    self.logger.info(
                        "Pubsub chanted to False in config, but not in GCP."
                    )
                    self.logger.info(
                        "Note: Budget API bug exists where pubsub will not be \
                                      removed, even though the API call succeeds."
                    )
                    ret_val = False
                    changed_budget["notifications_rule"] = {}

        return ret_val, changed_budget

    def create_budget(self, project):
        """Creates a GCP budget."""

        self.logger.info(f"Creating new budget {project.display_name}...")

        parent = self.billing_client.common_billing_account_path(
            project.billing_account_id
        )

        if project.include_credits:
            credit_types_treatment = "INCLUDE_ALL_CREDITS"
        else:
            credit_types_treatment = "EXCLUDE_ALL_CREDITS"

        if project.budget_type == "AMT":
            amount_dict = {
                "specified_amount": {
                    "currency_code": "USD",
                    "units": project.budget_amount,
                }
            }
        elif project.budget_type == "LASTMONTH":
            amount_dict = {"last_period_amount": {}}
        else:
            self.logger.error("Config value budget_type must be AMT or LASTMONTH")
            metrics.incr(
                "error_count",
                tags=["type:misconfig", f"project_id:{project.project_id}"],
            )
            return None

        threshold_rules = []
        for rule in project.threshold_rules:
            threshold_rules.append(
                {
                    "threshold_percent": rule["threshold_percent"],
                    "spend_basis": rule["spend_basis"],
                }
            )

        if project.pubsub:
            # Configure pubsub. Cannot be undone by future updates due to Budget API bug.
            # Currently only schema version 1.0 is supported
            notifications_rule = {
                "pubsub_topic": project.pubsub_topic,
                "schema_version": "1.0",
            }
        else:
            notifications_rule = {}

        budget = {
            "display_name": project.display_name,
            "budget_filter": {
                "projects": [f"projects/{project.project_id}"],
                "credit_types_treatment": credit_types_treatment,
            },
            "amount": amount_dict,
            "threshold_rules": threshold_rules,
            "notifications_rule": notifications_rule,
        }

        try:
            response = self.billing_client.create_budget(parent=parent, budget=budget)
            metrics.incr(
                "gcp_api_request_count",
                tags=["type:billing.create", f"project_id:{project.project_id}"],
            )
            return response
        except GoogleAPICallError as err:
            self.logger.error(
                f"Create budget request failed. \
                              GoogleAPICallError: {err}. Project id: {project.project_id}"
            )
            metrics.incr(
                "gcp_api_error_count",
                tags=[
                    "type:billing.create.apicall",
                    f"project_id:{project.project_id}",
                ],
            )
        except RetryError as err:
            self.logger.error(
                f"Request failed due to retryable error \
                              and retry attempts failed: {err}"
            )
            metrics.incr(
                "gcp_api_error_count",
                tags=["type:billing.create.retry", f"project_id:{project.project_id}"],
            )
        except ValueError as err:
            self.logger.error(
                f"Requst failed likely due to invalid parameters. ValueError: {err}"
            )
            metrics.incr(
                "gcp_api_error_count",
                tags=["type:billing.create.value", f"project_id:{project.project_id}"],
            )

    def update_budget(self, changed_budget):
        """Updates an existing GCP budget."""

        self.logger.info(f"Updating budget for {changed_budget['display_name']}...")

        try:
            # update_budget now expects a proto or dict with a budget key and update_mask key
            changed_budget_dict = {"budget": changed_budget}
            response = self.billing_client.update_budget(changed_budget_dict)
            metrics.incr(
                "gcp_api_request_count",
                tags=[
                    "type:billing.update",
                    f"display_name:{changed_budget['display_name']}",
                ],
            )
            return response
        except GoogleAPICallError as err:
            self.logger.error(
                f"Update budget request failed due to GoogleAPICallError: {err}. \
                              Budget was {changed_budget['display_name']}"
            )
            metrics.incr(
                "gcp_api_error_count",
                tags=[
                    "type:billing.update.apicall",
                    f"display_name:{changed_budget['display_name']}",
                ],
            )
        except RetryError as err:
            self.logger.error(
                f"Request failed due to retryable error \
                              and retry attempts failed: {err}"
            )
            metrics.incr(
                "gcp_api_error_count",
                tags=[
                    "type:billing.update.retry",
                    f"display_name:{changed_budget['display_name']}",
                ],
            )
        except ValueError as err:
            self.logger.error(
                f"Requst failed likely due to invalid parameters. ValueError: {err}"
            )
            metrics.incr(
                "gcp_api_error_count",
                tags=[
                    "type:billing.update.value",
                    f"display_name:{changed_budget['display_name']}",
                ],
            )

    def delete_budget(self, budget_id):
        """Deletes an existing GCP budget."""

        self.logger.info(f"Deleting budget for {budget_id}...")
        self.billing_client.delete_budget(name=budget_id)

    def get_and_update_or_create_budget(self, project):
        """
        Takes a ProjectBudget object constructed from the yaml config and does one of two things:
        1. Gets the budget, compares values with GCP and updates budget if changes have occurred
        2. Creates a budget in GCP

        Returns budget object
        """

        project_id = project.project_id
        project_number = self.get_project_number(project_id)

        budgets = self.get_budgets_by_project(project, project_number)

        if len(budgets) == 0:
            budget = self.create_budget(project)
            return budget
        elif len(budgets) >= 1:
            for budget in budgets:
                if budget.display_name == project.display_name:
                    # Found correct budget to compare, since we programatically create display names

                    # Google rpcs now use proto-plus which wrap raw proto. So now we cannot use
                    # older protobuf to dict libs or googles protobuf MessageToDict methods,
                    # unless we extract the raw .pb (protobuf) object wrapped inside
                    budget_dict = MessageToDict(
                        budget.__class__.pb(budget), preserving_proto_field_name=True
                    )
                    same, changed_budget = self.sync_config_with_gcp_budget(
                        project, budget_dict, project_number
                    )

                    if not same and changed_budget is not None:
                        self.logger.info(
                            f"Changes detected. Updating budget to {changed_budget}"
                        )
                        new_budget = self.update_budget(changed_budget)
                        return new_budget
                    elif changed_budget is None:
                        self.logger.error(
                            "Error while comparing config and gcp budget. Exiting..."
                        )
                        sys.exit(1)
                    else:
                        self.logger.debug(
                            f"No changes with budget {budget_dict['display_name']}"
                        )
                        return budget

            # No budgets for project matched the config, create new budget
            self.logger.info(
                f"No plutus budget found for {project.display_name}, creating..."
            )
            new_budget = self.create_budget(project)
            return new_budget
