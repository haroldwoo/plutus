# Similar to test_yaml_verify.py, but uses constructed dicts rather than loading them from file
from pytest import fixture
from plutus.budget_manager.verify import (
    verify_project_yaml,
    verify_parent_yaml,
    verify_labels_yaml,
    verify_default_yaml,
)


@fixture
def project_dict():
    dict = {
        "project_id": "some-project-id",
        "budget_type": "AMT",
        "budget_amount": 1000,
        "products": ["ALL"],
        "alert_emails": ["test@test.com", "test2@test.com"],
        "threshold_rules": [{"threshold_percent": 1.0, "spend_basis": "CURRENT_SPEND"}],
        "include_credits": False,
        "pubsub": True,
        "pubsub_topic": "projects/some-project/topics/some-topic",
    }
    return dict


@fixture
def parent_dict():
    dict = {
        "parent_folder_id": "some-parent-folder-id",
        "budget_type": "AMT",
        "budget_amount": 1000,
        "products": ["ALL"],
        "alert_emails": ["test@test.com", "test2@test.com"],
        "threshold_rules": [{"threshold_percent": 1.0, "spend_basis": "CURRENT_SPEND"}],
        "include_credits": False,
        "pubsub": True,
        "pubsub_topic": "projects/some-project/topics/some-topic",
    }
    return dict


@fixture
def label_dict():
    dict = {
        "label_list": [{"key": "value"}],
        "budget_type": "AMT",
        "budget_amount": 1000,
        "products": ["ALL"],
        "alert_emails": ["test@test.com", "test2@test.com"],
        "threshold_rules": [{"threshold_percent": 1.0, "spend_basis": "CURRENT_SPEND"}],
        "include_credits": False,
        "pubsub": True,
        "pubsub_topic": "projects/some-project/topics/some-topic",
    }
    return dict


@fixture
def default_dict():
    dict = {
        "budget_type": "AMT",
        "budget_amount": 1000,
        "products": ["ALL"],
        "alert_emails": ["test@test.com", "test2@test.com"],
        "threshold_rules": [{"threshold_percent": 1.0, "spend_basis": "CURRENT_SPEND"}],
        "include_credits": False,
        "pubsub": True,
        "pubsub_topic": "projects/some-project/topics/some-topic",
    }
    return dict


# Project id config tests
def test_yes_project_id(project_dict):
    assert verify_project_yaml(project_dict) is True


def test_no_project_id(project_dict):
    del project_dict["project_id"]
    assert verify_project_yaml(project_dict) is False


def test_wrong_project_id_type(project_dict):
    project_dict["project_id"] = 1234
    assert verify_project_yaml(project_dict) is False


def test_missing_budget_type(project_dict):
    del project_dict["budget_type"]
    assert verify_project_yaml(project_dict) is False


def test_missing_budget_amount(project_dict):
    del project_dict["budget_amount"]
    assert verify_project_yaml(project_dict) is False


def test_missing_threshold_rules(project_dict):
    del project_dict["threshold_rules"]
    assert verify_project_yaml(project_dict) is False


def test_missing_include_credits(project_dict):
    del project_dict["include_credits"]
    assert verify_project_yaml(project_dict) is False


def test_missing_pubsub(project_dict):
    del project_dict["pubsub"]
    assert verify_project_yaml(project_dict) is False


def test_user_configured_display_name(project_dict):
    project_dict["display_name"] = "user specified display name"
    assert verify_project_yaml(project_dict) is False


def test_budget_type_wrong_type(project_dict):
    project_dict["budget_type"] = 1234
    assert verify_project_yaml(project_dict) is False


def test_budget_amount_wrong_type(project_dict):
    project_dict["budget_amount"] = "foobar"
    assert verify_project_yaml(project_dict) is False


def test_pubsub_wrong_type(project_dict):
    project_dict["pubsub"] = "foobar"
    assert verify_project_yaml(project_dict) is False


def test_alert_emails_wrong_type(project_dict):
    project_dict["alert_emails"] = "foobar@test.com"
    assert verify_project_yaml(project_dict) is False


def test_threshold_rules_wrong_type(project_dict):
    project_dict["threshold_rules"] = "foobar"
    assert verify_project_yaml(project_dict) is False


def test_threshold_rules_invalid_spend_basis(project_dict):
    project_dict["threshold_rules"][0]["spend_basis"] = "foobar"
    assert verify_project_yaml(project_dict) is False


def test_threshold_percent_wrong_type(project_dict):
    project_dict["threshold_rules"][0]["threshold_percent"] = "foobar"
    assert verify_project_yaml(project_dict) is False


def test_threshold_rules_invalid_list_object(project_dict):
    del project_dict["threshold_rules"][0]["spend_basis"]
    assert verify_project_yaml(project_dict) is False


def test_pubsub_topic_wrong_type(project_dict):
    project_dict["pubsub_topic"] = 1234
    assert verify_project_yaml(project_dict) is False


# Parent folder config tests
def test_yes_parent_id(parent_dict):
    assert verify_parent_yaml(parent_dict) is True


def test_no_parent_id(parent_dict):
    del parent_dict["parent_folder_id"]
    assert verify_parent_yaml(parent_dict) is False


def test_parent_id_with_morekeys(parent_dict):
    parent_dict["project_id"] = "some-project-id"
    assert verify_parent_yaml(parent_dict) is False


# Labels config tests
def test_yes_labels(label_dict):
    assert verify_labels_yaml(label_dict) is True


def test_no_labels(label_dict):
    del label_dict["label_list"]
    assert verify_labels_yaml(label_dict) is False


def test_label_list_wrong_type(label_dict):
    label_dict["label_list"] = 1234
    assert verify_labels_yaml(label_dict) is False


def test_label_list_len(label_dict):
    label_dict["label_list"].append({"key2": "value2"})
    assert verify_labels_yaml(label_dict) is True


def test_label_list_obj_wrong_type(label_dict):
    label_dict["label_list"] = ["key, value"]
    assert verify_labels_yaml(label_dict) is False


def test_label_list_obj_wrong_type2(label_dict):
    label_dict["label_list"] = [{"key": "value", "key2": "value2"}]
    assert verify_labels_yaml(label_dict) is False


# Default config tests
def test_good_default(default_dict):
    assert verify_default_yaml(default_dict) is True


def test_add_project_id(default_dict):
    default_dict["project_id"] = "some-project-id"
    assert verify_default_yaml(default_dict) is False


def test_add_parent_folder_id(default_dict):
    default_dict["parent_folder_id"] = "some-parent-folder-id"
    assert verify_default_yaml(default_dict) is False


def test_add_label_list(default_dict):
    default_dict["label_list"] = [{"key": "value"}]
    assert verify_default_yaml(default_dict) is False
