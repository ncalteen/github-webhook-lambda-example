from socket import timeout
from aws_cdk import (
    aws_apigateway,
    aws_iam,
    aws_lambda,
    aws_lambda_python_alpha as aws_lambda_python,
    CfnOutput,
    Duration,
    Stack,
)
from constructs import Construct

class WebhookCdkStack(Stack):

    def __init__(self, scope: Construct, construct_id: str,
                 github_token_arn: str,
                 github_webhook_secret_arn: str,
                 github_user: str,
                 git_email: str,
                 git_name: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # WebhookCdkStack requires an ARN to the AWS Secrets Manager
        #   secret containing the SSH key used to authenticate to
        #   GitHub and make repository changes.
        # Raise exception if not present.
        if not github_token_arn or github_token_arn == "":
            raise Exception("No GitHub Token secret ARN provided!")
        
        if not github_webhook_secret_arn or github_webhook_secret_arn == "":
            raise Exception("No webhook secret provided!")
        
        if not github_user or github_user == "GITHUB_USER":
            raise Exception("No GitHub user provided!")
        
        if not git_email or git_email == "GITHUB_EMAIL":
            raise Exception("No git email provided!")
        
        if not git_name or git_name == "GITHUB_NAME":
            raise Exception("No git name provided!")

        # IAM role for AWS Lambda function that
        #   backs the API Gateway endpoint.
        lambda_role = aws_iam.Role(self, "github-lambda-role",
            assumed_by=aws_iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Lambda role for API Gateway integration function"
        )

        # Add basic AWS Lambda permissions for logging, metrics, etc.
        lambda_role.add_managed_policy(
            aws_iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
        )

        # Add permissions to get the GitHub SSH key secret.
        lambda_role.attach_inline_policy(
            aws_iam.Policy(self, "github-lambda-ssh-secret-policy",
                           statements=[
                               aws_iam.PolicyStatement(
                                   actions=[
                                       "secretsmanager:DescribeSecret",
                                       "secretsmanager:GetSecretValue"
                                   ],
                                   effect=aws_iam.Effect.ALLOW,
                                   resources=[
                                       github_token_arn,
                                       github_webhook_secret_arn
                                   ])
                           ])
        )

        # Function to handle events sent through API Gateway.
        lambda_function = aws_lambda_python.PythonFunction(self, "github-repo-created-event-handler",
            entry="lambda",
            index="index.py",
            handler="lambda_handler",
            runtime=aws_lambda.Runtime.PYTHON_3_9,
            description="Receives API Gateway events for GitHub repo creation",
            environment={
                "GITHUB_TOKEN_SECRET_ARN": github_token_arn,
                "GITHUB_WEBHOOK_SECRET_ARN": github_webhook_secret_arn,
                "GITHUB_USER": github_user,
                "GIT_EMAIL": git_email,
                "GIT_NAME": git_name,
                "RELEASE_VERSION": "0.1.0",
            },
            role=lambda_role,
            timeout=Duration.seconds(60)
        )

        # Add this layer to enable support for git commands in AWS Lambda.
        #   Source: https://github.com/lambci/git-lambda-layer
        #   TODO: Consider creating this in your own account if there's a need/concern.
        git_layer = aws_lambda.LayerVersion.from_layer_version_arn(self, "GitLayer",
                                                                   f"arn:aws:lambda:{self.region}:553035198032:layer:git-lambda2:8")
        lambda_function.add_layers(git_layer)

        # REST API to receive GitHub webhooks.
        rest_api = aws_apigateway.LambdaRestApi(self, "github-webook-api",
            description="Receives GitHub webhooks",
            deploy=True,
            handler=lambda_function,
            proxy=True,
            binary_media_types=["application/json"]
        )

        api_output = CfnOutput(self, "RESTAPIURLOutput", value=rest_api.url)
        api_output.override_logical_id(new_logical_id="PayloadURL")
