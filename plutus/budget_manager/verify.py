# Performs quick checking of config.yaml for github merges and also for budget monitor
from plutus.lib.constants import APP
import logging

log = logging.getLogger(f"{APP}.verify")


def verify_project_yaml(project_dict):
    if 'project_id' not in project_dict:
        log.error("Config error. 'project_id' key is missing.")
        return False
    elif not isinstance(project_dict['project_id'], str):
        log.error(f"Config error. 'project_id' value must be str. \
                  Got {project_dict['project_id']}.")
        return False
    else:
        ok = (_verify_budget_keys(project_dict) and _verify_budget_values(project_dict))
        return ok


def verify_parent_yaml(parent_dict):
    keys = ('project_id', 'label_list')
    for k in keys:
        if k in parent_dict:
            log.error("Config error. Parent config should not include project_id or label_list.")
            return False

    if 'parent_folder_id' not in parent_dict:
        log.error("Config error. 'parent_folder_id' key is missing.")
        return False
    else:
        ok = (_verify_budget_keys(parent_dict) and _verify_budget_values(parent_dict))
        return ok


def verify_labels_yaml(label_dict):
    keys = ('project_id', 'parent_folder_id')
    for k in keys:
        if k in label_dict:
            log.error("Config error. Label config should not \
                      include project_id or parent_folder_id.")
            return False

    if 'label_list' not in label_dict:
        log.error("Config error. 'label_list' key is missing.")
        return False
    elif not isinstance(label_dict['label_list'], list):
        log.error(f"Config error. 'label_list' value must be of type list. \
                  Got {label_dict['label_list']}.")
        return False
    elif len(label_dict['label_list']) == 0:
        log.error("Config error. 'label_list' length is 0.")
        return False
    else:
        for i in label_dict['label_list']:
            if not isinstance(i, dict):
                log.error(f"Config error. Labels in label_list must be of type dict. \
                          E.g. 'key':'value'. Got {i}.")
                return False
            elif len(i) != 1:
                log.error("Config error. Labels in label_list \
                          should be one k/v pair per line/entry.")
                return False

    ok = (_verify_budget_keys(label_dict) and _verify_budget_values(label_dict))
    return ok


def verify_default_yaml(default_dict):
    keys = ('project_id', 'parent_folder_id', 'label_list')
    for k in keys:
        if k in default_dict:
            log.error("Config error. Default config should not include \
                      project_id, parent_folder_id, or label_list.")
            return False

    ok = (_verify_budget_keys(default_dict) and _verify_budget_values(default_dict))
    return ok


def _verify_budget_keys(project_dict):
    # Required keys
    project_keys = ('budget_type', 'budget_amount', 'threshold_rules', 'include_credits', 'pubsub')
    if all(key in project_dict for key in project_keys):
        return True
    else:
        log.error(f"One or more of the following keys are missing: {project_keys}")
        return False


def _verify_budget_values(project_dict):
    if 'display_name' in project_dict:
        log.error("Config error. Key 'display_name' should not be configured by user.")
        return False

    if not isinstance(project_dict['budget_type'], str):
        log.error(f"Config error. budget_type {project_dict['budget_type']} must be type str.")
        return False

    if not isinstance(project_dict['budget_amount'], int):
        log.error(f"Config error. budget_amount {project_dict['budget_amount']} must be type int.")
        return False

    for key in ('include_credits', 'pubsub'):
        if not isinstance(project_dict[key], bool):
            log.error(f"Config error. {key} {project_dict[key]} must be of type bool.")
            return False

    if (project_dict['budget_type'] != "AMT") and (project_dict['budget_type'] != "LASTMONTH"):
        log.error(f"Config error. budget_type {project_dict['budget_type']} \
                  must be 'AMT' or 'LASTMONTH'")
        return False

    if 'products' in project_dict:
        if not isinstance(project_dict['products'], list):
            log.error(f"Config error. 'products' type {type(project_dict['products'])} \
                      must be of type list(str).")
            return False

    if 'alert_emails' in project_dict:
        if not isinstance(project_dict['alert_emails'], list):
            log.error(f"Config error. 'alert_emails' type {type(project_dict['alert_emails'])} \
                      must be of type list(str).")
            return False

    if 'threshold_rules' in project_dict:
        if not isinstance(project_dict['threshold_rules'], list):
            log.error(f"Config error. 'threshold_rules' type {type(project_dict['threshold_rules'])} \
                      must be of type list.")
            return False

        for rule in project_dict['threshold_rules']:
            if rule.get('spend_basis') and rule.get('threshold_percent'):
                if not (rule['spend_basis'] == 'CURRENT_SPEND' or
                        rule['spend_basis'] == 'FORECASTED_SPEND'):
                    log.error(f"Config error. 'spend_basis' must be either \
                              CURRENT_SPEND or FORECASTED_SPEND'. Got '{rule['spend_basis']}'.")
                    return False
                if not isinstance(rule['threshold_percent'], float):
                    log.error(f"Config error. 'threshold_percent' must be of type float. \
                              Got value '{rule['threshold_percent']}'")
                    log.error("Note: A value of 1.0 would represent 100%.")
                    return False
            else:
                log.error("Config error. 'threshold_rules' must contain a list \
                          of elements with 'threshold_percent' and 'spend_basis'.")
                return False

    if 'pubsub_topic' in project_dict:
        if not isinstance(project_dict['pubsub_topic'], str):
            log.error(f"Config error. 'pubsub_topic' must be of type str. \
                      Got {project_dict['pubsub_topic']}.")
            return False

    return True
