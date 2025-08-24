from aws_cdk import (
    Stack,
    RemovalPolicy,
    aws_s3 as s3,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_apigateway as apigw,
)
from constructs import Construct


class AppStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        firmware_bucket = s3.Bucket(
            self, "FirmwareBucket",

            # todo: remove in prod
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )

        metadata_table = dynamodb.Table(
            self, "MetadataTable",
            partition_key=dynamodb.Attribute(
                name="PK",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="SK",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY
        )

        ota_lambda = lambda_.Function(
            self, "OtaCheckFunction",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="handler.main",
            code=lambda_.Code.from_asset("lambda/ota-check-function"),
            environment={
                "TABLE_NAME": metadata_table.table_name,
                "BUCKET_NAME": firmware_bucket.bucket_name
            }
        )

        metadata_table.grant_read_data(ota_lambda)
        firmware_bucket.grant_read(ota_lambda)

        api = apigw.LambdaRestApi(
            self, "OtaApiEndpoint",
            handler=ota_lambda,
            proxy=False
        )

        check_for_update_resource = api.root.add_resource("check-for-update")
        check_for_update_resource.add_method("GET")