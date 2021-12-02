from plutus.lib.constants import PLUTUS_CONFIG_TYPE_PROJECT
from plutus.lib.gcp_helper import GcpHelper
from plutus.budget_manager.project_budget import ProjectBudget
from pytest import fixture


@fixture
def project():
    project_dict = {
        "project_id": "some-project-id",
        "budget_type": "AMT",
        "budget_amount": 1000,
        "products": ["ALL"],
        "alert_emails": ["test@test.com", "test2@test.com"],
        "threshold_rules": [
            {"threshold_percent": 1.1, "spend_basis": "CURRENT_SPEND"},
            {"threshold_percent": 1.2, "spend_basis": "FORECASTED_SPEND"},
        ],
        "include_credits": False,
        "pubsub": True,
        "pubsub_topic": "projects/some-project-id/topics/some-topic",
    }
    return ProjectBudget(
        project_dict,
        PLUTUS_CONFIG_TYPE_PROJECT,
        "foo-bar-123",
        "project/some-project/topics/foobar",
    )


def gen_budget_dict(
    project_id_or_num="some-project-id",
    credit_types_treatment="EXCLUDE_ALL_CREDITS",
    amount={"specified_amount": {"currency_code": "USD", "units": "1000"}},
):
    """
    Constructs a dict matching the protobuf_to_dict representation of a Gcp Budget
    returned from the API. The defaults make this budget dict match the project fixture above.
    """

    dict = {
        "name": "billingAccounts/foo-bar-123/budgets/some-budget-id-hash",
        "display_name": "plutus-doesnt-matter",
        "budget_filter": {
            "projects": ["projects/" + project_id_or_num],
            "credit_types_treatment": credit_types_treatment,
        },
        "amount": amount,
        "threshold_rules": [
            {"threshold_percent": 1.1, "spend_basis": "CURRENT_SPEND"},
            {"threshold_percent": 1.2, "spend_basis": "FORECASTED_SPEND"},
        ],
        "notifications_rule": {
            "pubsub_topic": "projects/some-project-id/topics/some-topic",
            "schema_version": "1.0",
        },
        "etag": "xxxyyyzzz",
    }
    return dict


# Initialize with no gcp clients
gcp_helper = GcpHelper(None, None)


def test_match(project):
    # Test when only project id matches
    budget_dict = gen_budget_dict()
    same, returned_budget = gcp_helper.sync_config_with_gcp_budget(
        project, budget_dict, "12345"
    )
    assert same is True
    # No changes to returned budget dict
    assert returned_budget == budget_dict

    # Test when only project number matches
    budget_dict = gen_budget_dict(project_id_or_num="12345")
    same, returned_budget = gcp_helper.sync_config_with_gcp_budget(
        project, budget_dict, "12345"
    )
    assert same is True
    assert returned_budget == budget_dict


def test_wrong_project_id_and_num(project):
    budget_dict = gen_budget_dict(project_id_or_num="different-project-id")
    same, returned_budget = gcp_helper.sync_config_with_gcp_budget(
        project, budget_dict, "12345"
    )
    assert same is False
    assert returned_budget != budget_dict
    assert returned_budget is None


def test_multiple_projects(project):
    # Fails if >1 project, due to current Budget API restriction - only 0(ALL) or 1 project
    # Also for plutus we assume budgets will never span more than 1 project
    budget_dict = gen_budget_dict()
    budget_dict["budget_filter"]["projects"].append("projects/another-project-id")
    same, returned_budget = gcp_helper.sync_config_with_gcp_budget(
        project, budget_dict, "12345"
    )
    assert same is False
    assert returned_budget != budget_dict
    assert returned_budget is None


def test_change_amt_to_lastmonth(project):
    budget_dict = gen_budget_dict()
    # Overwrite configured project type to LASTMONTH
    project.budget_type = "LASTMONTH"
    same, returned_budget = gcp_helper.sync_config_with_gcp_budget(
        project, budget_dict, "12345"
    )
    assert same is False
    assert returned_budget != budget_dict
    assert returned_budget["amount"] == {"last_period_amount": {}}


def test_change_from_lastmonth_to_amt(project):
    # GCP budget is set to LASTMONTH, project config is set to AMT
    budget_dict = gen_budget_dict(amount={"last_period_amount": {}})
    same, returned_budget = gcp_helper.sync_config_with_gcp_budget(
        project, budget_dict, "12345"
    )
    assert same is False
    assert returned_budget != budget_dict
    assert returned_budget["amount"] == {
        "specified_amount": {"currency_code": "USD", "units": 1000}
    }


def test_non_usd(project):
    budget_dict = gen_budget_dict(
        amount={"specified_amount": {"currency_code": "CAD", "units": "1000"}}
    )
    same, returned_budget = gcp_helper.sync_config_with_gcp_budget(
        project, budget_dict, "12345"
    )
    assert same is False
    assert returned_budget != budget_dict
    assert returned_budget is None


def test_change_units(project):
    # Budget is set to 2k in GCP, 1K in project config
    amount = {"specified_amount": {"currency_code": "USD", "units": "2000"}}
    budget_dict = gen_budget_dict(amount=amount)
    same, returned_budget = gcp_helper.sync_config_with_gcp_budget(
        project, budget_dict, "12345"
    )
    assert same is False
    assert returned_budget != budget_dict
    # Assert that the value has now changed to reflect the project config of 1k
    assert returned_budget["amount"] == {
        "specified_amount": {"currency_code": "USD", "units": "1000"}
    }


def test_wrong_budget_type(project):
    budget_dict = gen_budget_dict()
    project.budget_type = "NON_AMT_OR_LASTMONTH"
    same, returned_budget = gcp_helper.sync_config_with_gcp_budget(
        project, budget_dict, "12345"
    )
    assert same is False
    assert returned_budget is None


def test_toggle_include_credits_true(project):
    budget_dict = gen_budget_dict()
    project.include_credits = True
    assert (
        budget_dict["budget_filter"]["credit_types_treatment"] == "EXCLUDE_ALL_CREDITS"
    )
    same, returned_budget = gcp_helper.sync_config_with_gcp_budget(
        project, budget_dict, "12345"
    )
    assert same is False
    assert (
        returned_budget["budget_filter"]["credit_types_treatment"]
        == "INCLUDE_ALL_CREDITS"
    )


def test_toggle_include_credits_false(project):
    # Set budget in GCP to include credits, project config set to False to toggle
    budget_dict = gen_budget_dict()
    budget_dict["budget_filter"]["credit_types_treatment"] = "INCLUDE_ALL_CREDITS"
    same, returned_budget = gcp_helper.sync_config_with_gcp_budget(
        project, budget_dict, "12345"
    )
    assert same is False
    assert (
        returned_budget["budget_filter"]["credit_types_treatment"]
        == "EXCLUDE_ALL_CREDITS"
    )


def test_update_threshold_rules(project):
    budget_dict = gen_budget_dict()
    project.threshold_rules.append(
        {"threshold_percent": 1.3, "spend_basis": "CURRENT_SPEND"}
    )
    assert len(budget_dict["threshold_rules"]) == 2
    same, returned_budget = gcp_helper.sync_config_with_gcp_budget(
        project, budget_dict, "12345"
    )
    assert same is False
    assert len(returned_budget["threshold_rules"]) == 3

    project_list = sorted(
        project.threshold_rules, key=lambda x: x["threshold_percent"], reverse=True
    )
    budget_list = sorted(
        returned_budget["threshold_rules"],
        key=lambda x: x["threshold_percent"],
        reverse=True,
    )
    assert project_list == budget_list


def test_toggle_pubsub_true(project):
    budget_dict = gen_budget_dict()
    # Update budget in GCP to no pubsub
    budget_dict["notifications_rule"] = {}
    assert project.pubsub is True
    assert budget_dict["notifications_rule"] == {}
    same, returned_budget = gcp_helper.sync_config_with_gcp_budget(
        project, budget_dict, "12345"
    )
    assert same is False
    assert returned_budget["notifications_rule"] == {
        "pubsub_topic": "projects/some-project-id/topics/some-topic",
        "schema_version": "1.0",
    }


def test_toggle_pubsub_false(project):
    # Works in test, and API call will succeed, but budget not be updated to rm pubsub(API bug)
    budget_dict = gen_budget_dict()
    project.pubsub = False
    assert budget_dict["notifications_rule"] == {
        "pubsub_topic": "projects/some-project-id/topics/some-topic",
        "schema_version": "1.0",
    }
    same, returned_budget = gcp_helper.sync_config_with_gcp_budget(
        project, budget_dict, "12345"
    )
    assert same is False
    assert returned_budget["notifications_rule"] == {}
