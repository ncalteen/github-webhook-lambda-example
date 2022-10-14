import base64
import boto3
import hashlib
import hmac
import json
import os
import re

from api import APIClient
from typing import Dict
from urllib.parse import unquote
from vars import lambda_response

# Run these outside the handler, since they only
#   needs to run in the Lambda container once.

# Initialize Boto3 client.
secrets_client = boto3.client('secretsmanager')

# Get the GitHub token from AWS Secrets Manager.
github_token_secret_arn = os.environ.get("GITHUB_TOKEN_SECRET_ARN")
github_token = secrets_client.get_secret_value(SecretId=github_token_secret_arn).get('SecretString')
github_token = json.loads(github_token).get('github_token')

# Get the webhook secret as well.
github_webhook_secret_arn = os.environ.get("GITHUB_WEBHOOK_SECRET_ARN")
github_secret = secrets_client.get_secret_value(SecretId=github_webhook_secret_arn).get('SecretString')
github_secret = json.loads(github_secret).get('webhook_secret')

github_user = os.environ.get("GITHUB_USER")
git_email = os.environ.get("GIT_EMAIL")
git_name = os.environ.get("GIT_NAME")

# Create a basic client for API calls.
client = APIClient(github_token=github_token)


def lambda_handler(event: Dict, context: Dict) -> Dict:
    """
    Amazon API Gateway proxies requests to the REST endpoint
      directly to this function (regardless of resource and method).

    The GitHub webhook payload is stored in event['body'].
    The webhook payload may be Base64 encoded.
    
    Webhook payload structure can be found here:
      https://docs.github.com/en/developers/webhooks-and-events/webhooks/webhook-events-and-payloads#repository

    Print statements log to Amazon CloudWatch Logs.
      https://docs.aws.amazon.com/lambda/latest/dg/monitoring-cloudwatchlogs.html
    
    Args:
        event: The input event from GitHub
        context: The Lambda function context
    
    Returns:
        The Lambda function response JSON
    """

    # Get the GitHub webhook out of the API Gateway request body.
    if event.get('isBase64Encoded'):
        body = base64.b64decode(event.get('body'))
    else:
        body = event.get('body')
    webhook_obj = json.loads(body)

    # Repository REST reference:
    #   https://docs.github.com/en/rest/reference/repos
    action = webhook_obj.get('action')
    repository_name = webhook_obj.get('repository').get('name')
    repository_full_name = webhook_obj.get('repository').get('full_name')
    repository_git_url = webhook_obj.get('repository').get('git_url')
    repository_clone_url = webhook_obj.get('repository').get('clone_url')

    print(f"Action: {action}")
    print(f"Repository: {repository_full_name}")
    print(f"Organization: {webhook_obj.get('organization').get('login')}")
    print(f"Repository Git URL: {repository_git_url}")
    print(f"Repository Clone URL: {repository_clone_url}")
    
    # Validate the signature of the request with the
    #   secret set in the webhook.
    signatures_match = verify_signatures(signature_header=event.get('headers').get('X-Hub-Signature'),
                                         body=body)
    if not signatures_match:
        # Invalid access attempt.
        print("Signature mismatch!")
        lambda_response['statusCode'] = 403
        lambda_response['body'] = json.dumps('Access Denied')
        return lambda_response
    
    if action != 'created':
        # Right now only `created` events are handled.
        print("Unsupported action. Exiting...")
        return lambda_response

    # Get the list of branches.
    #   https://docs.github.com/en/rest/reference/branches#list-branches
    branches = client.get(url=f"/repos/{repository_full_name}/branches")

    # Check if there are existing branches.
    if not branches:
        # There is not, create one.
        print("No branches. Creating default.")
        create_first_branch(repository_name=repository_name,
                            repository_clone_url=repository_clone_url)
        print("Default created.")

    # Get the list of branches again.
    branches = client.get(url=f"/repos/{repository_full_name}/branches")

    # Enable code reviews for all branches.
    #   https://docs.github.com/en/rest/reference/branches#list-branches
    for branch in branches:
        print(f"Adding protection to: {branch.get('name')}")
        edit_branch_protection(repository_full_name=repository_full_name,
                               branch_name=branch.get('name'))

    # Create an issue noting protections that were added.
    #   https://docs.github.com/en/rest/reference/issues#create-an-issue
    print("Creating issue.")
    create_issue(repository_full_name=repository_full_name)

    print("Done!")
    return lambda_response


def verify_signatures(signature_header: str, body: str) -> bool:
    """
    Checks if the request signature matches the expected signature
    
    Args:
        signature_header: The signature header from GitHub
        body: The request body
        
    Returns:
        True if the request signature matches the calculated one, false otherwise
    """
    incoming_signature = re.sub(r'^sha1=', '', signature_header)

    calculated_signature = hmac.new(key=bytes(github_secret, 'utf-8'),
                                    msg=body,
                                    digestmod=hashlib.sha1).hexdigest()

    return incoming_signature == calculated_signature


def create_first_branch(repository_name: str, repository_clone_url: str) -> None:
    """
    Creates an initial branch in the provided git repo.
    
    Initial commit will contain a basic README.md file.
    
    Args:
        repository_name: The repository name (without the organization name)
        repository_clone_url: The HTTPS clone URL
    """
    # Remove any possible duplicate repo folder.
    print("Removing old directories")
    os.system(f"rm -rf /tmp/{repository_name}")

    # Make a new directory for the repo.
    print("Creating new directory to clone into")
    os.mkdir(f"/tmp/{repository_name}")
    
    # Add the token to the clone URL
    tokenized_url = repository_clone_url.replace('//', f'//{github_user}:{github_token}@')

    # Clone the repo.
    print("Cloning the repository")
    os.system(f"git -C /tmp clone {tokenized_url} /tmp/{repository_name}")

    # Configure git user
    print("Configuring git user")
    os.system(f"git -C /tmp/{repository_name} config --local user.email '{git_email}'")
    os.system(f"git -C /tmp/{repository_name} config --local user.name '{git_name}'")

    # Copy the initial README.md file into the repo.
    print("Copying README.md into repository")
    os.system(f"cp ./README.md /tmp/{repository_name}")

    # Add the README to the git index.
    print("Adding README.md to index")
    os.system(f"git -C /tmp/{repository_name} add README.md")

    # Commit the added file.
    print("Committing the file")
    os.system('git -C {} commit -m "Initial commit"'.format(f"/tmp/{repository_name}"))

    # Push the branch to the remote.
    push_url = repository_clone_url.replace("github.com", f"{github_token}@github.com")
    print(f"Pushing to remote: {push_url}")
    os.system(f"git -C /tmp/{repository_name} push {push_url}")


def edit_branch_protection(repository_full_name: str, branch_name: str) -> None:
    """Adds branch protection to a repository branch
    
    Args:
        repository_full_name: The repository name (with the organization name)
        branch_name: The name of the branch to modify
    """
    data = {
        "required_status_checks": None,
        "enforce_admins": True,
        "required_pull_request_reviews": {
            "dismissal_restrictions": {},
            "dismiss_stale_reviews": False,
            "require_code_owner_reviews": True,
            "required_approving_review_count": 1,
            "bypass_pull_request_allowances": {},
        },
        "restrictions": None
    }

    response = client.put(f"/repos/{repository_full_name}/branches/{branch_name}/protection",
                          data=data)
    
    if response.get('message') == 'Upgrade to GitHub Pro or make this repository public to enable this feature.':
        print('Trying to add branch protection to a private repository.')


def create_issue(repository_full_name: str) -> None:
    """Creates an issue in a repository
    
    Args:
        repository_full_name: The name of the repository (with the organization name)
    """
    data = {
        "title": "Repository automatically protected",
        "body": f"""This repository has been modified to include the following settings:

* Require a pull request before merging
* Require 1 approval before merging
* Require review from Code Owners

Refer to [GitHub protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/defining-the-mergeability-of-pull-requests/about-protected-branches) for more information.

Tagging @{github_user}
""",
    }
    
    _ = client.post(f"/repos/{repository_full_name}/issues",
                    data=data)
