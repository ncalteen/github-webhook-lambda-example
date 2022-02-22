import json


# Output must be returned in the format mentioned below:
#   https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html#api-gateway-simple-proxy-for-lambda-output-format
lambda_response = {
    "isBase64Encoded": False,
    "statusCode": 200,
    "headers": {
        "Content-Type": "application/json",
    },
    "body": json.dumps({
        "Status": "OK"
    })
}
