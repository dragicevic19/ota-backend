import os
import json
import boto3
from botocore.exceptions import ClientError
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import load_pem_private_key

BUCKET_NAME = os.environ.get('BUCKET_NAME')
TABLE_NAME = os.environ.get('TABLE_NAME')
PRIVATE_KEY_SECRET_ARN = os.environ.get('PRIVATE_KEY_SECRET_ARN')

s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
secrets_manager = boto3.client('secretsmanager')
table = dynamodb.Table(TABLE_NAME)


def get_private_key():
    response = secrets_manager.get_secret_value(SecretId=PRIVATE_KEY_SECRET_ARN)
    return response['SecretString'].encode('utf-8')


def main(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        device_type = body.get('deviceType')
        version = body.get('version')
        group = body.get('group')
        release_notes = body.get('release_notes')

        if not all([device_type, version, group]):
            return {'statusCode': 400, 'body': json.dumps({'message': 'deviceType, version, and group are required.'})}

        firmware_key = f"{device_type}/{version}/firmware.bin"
        signature_key = f"{device_type}/{version}/firmware.sig"

        # 1. Download .bin file from S3 in a temp memory
        tmp_firmware_path = f"/tmp/{version}.bin"
        s3_client.download_file(BUCKET_NAME, firmware_key, tmp_firmware_path)

        # 2. Get private key
        private_key_pem = get_private_key()
        private_key = load_pem_private_key(private_key_pem, password=None)

        # 3. Digital signature
        with open(tmp_firmware_path, "rb") as f:
            firmware_bytes = f.read()

        signature = private_key.sign(firmware_bytes, ec.ECDSA(hashes.SHA256()))

        # 4. Upload signature to S3
        s3_client.put_object(Bucket=BUCKET_NAME, Key=signature_key, Body=signature)

        # 5. Update DynamoDB
        version_item = {
            'PK': f"DEVICE_TYPE#{device_type}",
            'SK': f"VERSION#{version}",
            'version_number': version,
            's3_key_firmware': firmware_key,
            's3_key_signature': signature_key,
            'release_notes': release_notes or 'No description provided.'
        }

        table.put_item(Item=version_item)

        # Update "pointer" for deployment group
        table.update_item(
            Key={'PK': f"DEVICE_TYPE#{device_type}", 'SK': f"GROUP#{group}"},
            UpdateExpression="SET version_number = :v, s3_key_firmware = :fk, s3_key_signature = :sk, release_notes = :rn",
            ExpressionAttributeValues={
                ':v': version_item['version_number'],
                ':fk': version_item['s3_key_firmware'],
                ':sk': version_item['s3_key_signature'],
                ':rn': version_item['release_notes']
            }
        )

        return {
            'statusCode': 200,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Firmware successfully signed and deployed.'})
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {'statusCode': 500, 'body': json.dumps({'message': f'Internal server error: {str(e)}'})}