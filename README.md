# plutus

GCP cost monitoring. Budget and Quota monitoring/alerting.

![](images/plutus-arch2.png)

## Components:

Budget manager - Using yaml configuration, will GetAndUpdateOrCreate() budgets. Additional state is also saved in SQL.

Budget monitor - Pubsub consumer that will alert to various channels based on thresholds.

(WIP) Project manager, Quota monitor, Billing manager, Quota manager

# Configuration
To add a new budget, simply create a PR to the https://github.com/mozilla-services/dataops/blob/main/plutus/config.yaml config file. (After merging the PR, CircleCI will sync this file to GCS, and the budget manager in GKE will sync budget changes every 10th minute).

Every plutus budget will only monitor a single GCP project. But you can use the parent folder ID or labels to configure multiple budgets with a single yaml configuration entry.

You can refer to examples/sample_config.yaml for a layout example. Configuration is broken into subsections:

## projects
Create a single budget for a single project

| Name | Description | Type | Default | Required |
|------|-------------|:----:|:-----:|:-----:|
| project\_id | GCP Project ID | string | n/a | yes |

## parent_folders
Creates a budget for every project that is a direct descendent of the parent folder

| Name | Description | Type | Default | Required |
|------|-------------|:----:|:-----:|:-----:|
| parent\_folder\_id | GCP Parent Folder ID (e.g. 1234567890123) | string | n/a | yes |

## labels
Create a budget for every project that matches the labels

| Name | Description | Type | Default | Required |
|------|-------------|:----:|:-----:|:-----:|
| label\_list | List of kv pairs matching GCP project labels, one per line. E.g. 'environment': 'prod'. See example config.yaml for more details. | list | n/a | yes |

## default
WIP - not implemented in the first release.
No default specific parameters. Refer to common configuration options below.

## Common configuration options

These options will be configured for each subsection (projects, parent_folders, labels, default).

| Name | Description | Type | Default | Required |
|------|-------------|:----:|:-----:|:-----:|
| budget\_type | Either 'AMT' or 'LASTMONTH' | string | n/a | yes |
| budget\_amount | Threshold amount in USD | string | n/a | yes |
| products | GCP products to monitor. Currenlty only 'ALL' is supported | List(string) | 'ALL' | no |
| alert\_emails | Emails to send alerts to. This will be unioned with the owners on the GCP project | List(string) | n/a | no |
| threshold\_rules | Threshold budget rules. A list of objects containing 'threshold\_percent' and 'spend\_basis' keys/value pairs. Threshold percent describes when to send an email to GCP Billing admins (1.0 means 100% of the budget\_amount. Spend basis is either 'CURRENT_SPEND' or 'FORECASTED_SPEND' | List(object) | n/a | yes |
| include\_credits | Whether to include GCP credits towards the running budget total | bool | False | yes |
| pubsub | Whether to send budget alerts to pubsub. This will be used by the budget monitor to send alerts via email, slack, pagerduty  | bool | False | yes |
| pubsub\_topic | Format projects/PROJECTID/topics/TOPICNAME | string | projects/moz-fx-data-dataops/topics/plutus-budget-notifications | no |
| alert\_slack\_channel\_id | Slack channel id for alert notifications | string | 'G01548794SE' | no | 

## Development

`make build` will build containers

`make up` will run the statsd and mysql containers

`docker run --network=host plutus_app:latest --billing-account-id xxx --dry-run` will run the application in dry run mode

`docker run --network=host plutus_app:latest --billing-account-id xxx` will run the application in a semi prod fashion (using local mysql, local config file in the container, but actually run GCP API commands to update budgets.)

Note: everytime you modify the config.yaml or any code, you will need to run a make build again (the container will copy contents of your local working dir into it's /app dir. So usually the testing cycle is: make changes, `make build`, then `docker run`.


### Important notes: 
- Currently there is a bug with the budgets api updatebudget call where if you set Pubsub to True, and later to False, the API will not reflect this change.
- There is also another bug in the python resource manager client where listing projects by more than one label returns a union of projects rather than an intersection. So if using labels, restrict it to a single label until this is resolved.
