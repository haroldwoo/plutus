-- To be ran on mysql

CREATE DATABASE IF NOT EXISTS plutus;

USE plutus;

CREATE TABLE IF NOT EXISTS budgets (
       budget_id VARCHAR(255) PRIMARY KEY NOT NULL,
       display_name VARCHAR(255) NOT NULL,
       project_id VARCHAR(255) NOT NULL,
       project_number VARCHAR(255) NOT NULL,
       products VARCHAR(255),
       budget_type VARCHAR(255) NOT NULL,
       budget_amount DOUBLE NOT NULL,
       include_credits BOOLEAN NOT NULL,
       pubsub BOOLEAN NOT NULL,
       pubsub_topic VARCHAR(255),
       owner_emails VARCHAR(255),
       created_date DATETIME NOT NULL,
       last_modified DATETIME NOT NULL,
       config_type VARCHAR(255) NOT NULL,
       alert_slack_channel_id VARCHAR(255),
       col_1 VARCHAR(255),
       col_2 VARCHAR(255),
       col_3 VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS alerts (
       budget_id VARCHAR(255) PRIMARY KEY NOT NULL,
       last_alert DATETIME NOT NULL,
       col_1 VARCHAR(255),
       col_2 VARCHAR(255),
       col_3 VARCHAR(255)
);


CREATE TABLE IF NOT EXISTS projects (
       project_id VARCHAR(255) PRIMARY KEY NOT NULL,
       project_number VARCHAR(255) NOT NULL,
       project_name VARCHAR(255),
       parent_id VARCHAR(255),
       created_time DATETIME NOT NULL,
       last_modified DATETIME NOT NULL,
       lifecycle_state VARCHAR(255) NOT NULL,
       deprecated BOOLEAN,
       owner_emails VARCHAR(255),
       project_type VARCHAR(255),
       labels VARCHAR(255),
       tag_1 VARCHAR(255),
       tag_2 VARCHAR(255),
       tag_3 VARCHAR(255),
       col_1 VARCHAR(255),
       col_2 VARCHAR(255),
       col_3 VARCHAR(255)
);
