from aws_cdk import (
    Stack,
    RemovalPolicy,
    aws_s3 as s3,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_apigateway as apigw, Duration, SecretValue,
)
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct


class AppStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        deployed_frontend_url = "https://d3gmoy110yyqcm.cloudfront.net/"

        firmware_bucket = s3.Bucket(
            self, "FirmwareBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            cors=[
                s3.CorsRule(
                    allowed_methods=[
                        s3.HttpMethods.GET,
                        s3.HttpMethods.PUT,
                        s3.HttpMethods.POST,
                        s3.HttpMethods.HEAD
                    ],
                    allowed_origins=["*"],
                    allowed_headers=["*"],
                    exposed_headers=[]
                )
            ]
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

        cors_options = apigw.CorsOptions(
            allow_origins=apigw.Cors.ALL_ORIGINS,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type", "Authorization"]
        )

        api = apigw.LambdaRestApi(
            self, "OtaApiEndpoint",
            handler=ota_lambda,
            proxy=False,
            default_cors_preflight_options=cors_options
        )

        check_for_update_resource = api.root.add_resource("check-for-update")
        check_for_update_resource.add_method("GET")

        list_devices_lambda = lambda_.Function(
            self, "ListDeviceTypesFunction",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="handler.main",
            code=lambda_.Code.from_asset("lambda/get-device-types"),
            environment={
                "TABLE_NAME": metadata_table.table_name
            }
        )

        metadata_table.grant_read_data(list_devices_lambda)

        device_types_resource = api.root.add_resource("device-types")
        device_types_resource.add_method(
            "GET",
            apigw.LambdaIntegration(list_devices_lambda)
        )

        get_device_details_lambda = lambda_.Function(
            self, "GetDeviceTypeDetailsFunction",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="handler.main",
            code=lambda_.Code.from_asset("lambda/get-device-type-details"),
            environment={"TABLE_NAME": metadata_table.table_name}
        )

        metadata_table.grant_read_data(get_device_details_lambda)

        device_type_id_resource = device_types_resource.add_resource("{deviceTypeId}")
        device_type_id_resource.add_method(
            "GET",
            apigw.LambdaIntegration(get_device_details_lambda)
        )


        crypto_layer = lambda_.LayerVersion(
            self, "CryptoLayer",
            code=lambda_.Code.from_asset("lambda_layer/cryptography_layer.zip"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_9],
            description="A layer to include the cryptography library"
        )

        with open("secrets/private_key.pem", "r") as f:
            private_key_value = f.read()

        private_key_secret = secretsmanager.Secret(
            self, "OtaPrivateKeySecret",
            secret_name="ota/EcdsaPrivateKeyCDK",
            secret_string_value=SecretValue.unsafe_plain_text(private_key_value)
        )

        generate_url_lambda = lambda_.Function(
            self, "GenerateUploadUrlFunction",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="handler.main",
            code=lambda_.Code.from_asset("lambda/generate-upload-url"),
            environment={"BUCKET_NAME": firmware_bucket.bucket_name}
        )
        firmware_bucket.grant_put(generate_url_lambda)

        finalize_upload_lambda = lambda_.Function(
            self, "FinalizeUploadFunction",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="handler.main",
            code=lambda_.Code.from_asset("lambda/finalize-upload"),
            environment={
                "BUCKET_NAME": firmware_bucket.bucket_name,
                "TABLE_NAME": metadata_table.table_name,
                "PRIVATE_KEY_SECRET_ARN": private_key_secret.secret_arn
            },
            layers=[crypto_layer],
            timeout=Duration.seconds(30)
        )

        firmware_bucket.grant_read_write(finalize_upload_lambda)
        metadata_table.grant_write_data(finalize_upload_lambda)
        private_key_secret.grant_read(finalize_upload_lambda)

        generate_url_resource = api.root.add_resource("generate-upload-url")
        generate_url_resource.add_method("POST", apigw.LambdaIntegration(generate_url_lambda))

        finalize_upload_resource = api.root.add_resource("finalize-upload")
        finalize_upload_resource.add_method("POST", apigw.LambdaIntegration(finalize_upload_lambda))
