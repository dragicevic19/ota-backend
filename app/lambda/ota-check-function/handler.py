import os
import json
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError


TABLE_NAME = os.environ.get('TABLE_NAME')
BUCKET_NAME = os.environ.get('BUCKET_NAME')

S3_CONFIG = Config(
    signature_version='s3v4',
    region_name=os.environ.get('AWS_REGION'),
    s3={'addressing_style': 'virtual'}
)
s3_client = boto3.client('s3', config=S3_CONFIG)
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(TABLE_NAME)


def generate_presigned_url(bucket_name, object_key, expiration=60):
    print(f"Generating pre-signed URL for key: {object_key}")
    try:
        response = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': object_key},
            ExpiresIn=expiration
        )
        return response
    except ClientError as e:
        print(f"Error while generating pre-signed URLs: {e}")
        return None


def main(event, context):
    try:
        params = event.get('queryStringParameters', {})
        current_version = params.get('current_version')
        device_type = params.get('device_type', 'test-device')
        deployment_group = params.get('group', 'production')

        if not current_version:
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'Query parameter <current_version> is required.'})
            }

        print(f"Device '{device_type}' (deployment group '{deployment_group}') and current_version: {current_version} is checking for updates...")

        # find active version for this group
        group_pk = f"DEVICE_TYPE#{device_type}"
        group_sk = f"GROUP#{deployment_group}"

        response = table.get_item(Key={'PK': group_pk, 'SK': group_sk})
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'body': json.dumps({'message': f"Deployment group '{deployment_group}' not found."})
            }

        active_version_info = response['Item']
        active_version_number = active_version_info.get('version_number')
        print(f"Active version for this group: {active_version_number}")

        if not active_version_number or active_version_number == current_version:
            print("Device is up to date.")
            return {'statusCode': 200, 'body': json.dumps({'update': False})}

        firmware_key = active_version_info.get('s3_key_firmware')
        signature_key = active_version_info.get('s3_key_signature')

        if not firmware_key or not signature_key:
            return {
                'statusCode': 500,
                'body': json.dumps({'message': 'Missing S3 keys in the table.'})
            }

        firmware_presigned_url = generate_presigned_url(BUCKET_NAME, firmware_key)
        signature_presigned_url = generate_presigned_url(BUCKET_NAME, signature_key)

        if not firmware_presigned_url or not signature_presigned_url:
            return {
                'statusCode': 500,
                'body': json.dumps({'message': 'Error while generating S3 pre-signed URLs.'})
            }

        return {
            'statusCode': 200,
            'body': json.dumps({
                'update': True,
                'version': active_version_number,
                'url': firmware_presigned_url,
                'signature_url': signature_presigned_url
            })
        }

    except Exception as e:
        print(f"Unknown error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'Internal server error'})
        }
