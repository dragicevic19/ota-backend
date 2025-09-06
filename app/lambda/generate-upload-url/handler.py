import os
import json
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

BUCKET_NAME = os.environ.get('BUCKET_NAME')
S3_CONFIG = Config(
    signature_version='s3v4',
    region_name=os.environ.get('AWS_REGION'),
    s3={'addressing_style': 'virtual'}
)

s3_client = boto3.client('s3', config=S3_CONFIG)


def main(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        device_type = body.get('deviceType')
        version = body.get('version')

        if not device_type or not version:
            return {'statusCode': 400, 'body': json.dumps({'message': 'deviceType and version are required.'})}

        object_key = f"{device_type}/{version}/firmware.bin"

        upload_url = s3_client.generate_presigned_url(
            ClientMethod='put_object',
            Params={'Bucket': BUCKET_NAME, 'Key': object_key, 'ContentType': 'application/octet-stream'},
            ExpiresIn=300  # URL važi 5 minuta
        )

        return {
            'statusCode': 200,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'uploadUrl': upload_url})
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {'statusCode': 500, 'body': json.dumps({'message': 'Internal server error.'})}