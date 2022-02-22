#!/usr/bin/env python3
import aws_cdk as cdk

from webhook_cdk.webhook_cdk_stack import WebhookCdkStack

# WebhookCdkStack requires an ARN to the AWS Secrets Manager
#   secret containing the personal access token used to
#   authenticate to GitHub and make repository changes.
github_token_arn = "arn:aws:secretsmanager:REGION:ACCOUNT:secret:SECRET_NAME"

# WebhookCdkStack requires the secret that will be used
#   when creating the webhook in the GitHub console.
github_webhook_secret_arn = "arn:aws:secretsmanager:REGION:ACCOUNT:secret:SECRET_NAME"

# The GitHub user account to tag in issues when
#   a new repository is created.
github_user = "GITHUB_USER"

# The email and name to associate with the initial commit.
# Used in Lambda during `git configure`.
git_email = "GIT_EMAIL"
git_name = "GIT_NAME"

app = cdk.App()
WebhookCdkStack(scope=app,
                construct_id="WebhookCdkStack",
                github_token_arn=github_token_arn,
                github_webhook_secret_arn=github_webhook_secret_arn,
                github_user=github_user,
                git_email=git_email,
                git_name=git_name)

app.synth()
