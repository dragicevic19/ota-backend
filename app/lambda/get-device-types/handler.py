import os
import json
import boto3
from botocore.exceptions import ClientError
from collections import defaultdict

TABLE_NAME = os.environ.get('TABLE_NAME')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(TABLE_NAME)


def main(event, context):
    try:
        response = table.scan()

        items = response.get('Items', [])

        device_type_data = defaultdict(dict)

        for item in items:
            pk = item.get('PK', '')
            sk = item.get('SK', '')

            if not pk.startswith('DEVICE_TYPE#'):
                continue

            device_type_id = pk.split('#', 1)[1]

            device_type_data[device_type_id]['id'] = device_type_id
            device_type_data[device_type_id]['device_id'] = device_type_id
            device_type_data[device_type_id]['name'] = device_type_id.replace('-', ' ').title()

            if sk == 'GROUP#production':
                version = item.get('version_number')
                if version:
                    device_type_data[device_type_id]['current_firmware_version'] = version

        formatted_devices = []
        for dt_id, data in device_type_data.items():
            formatted_devices.append({
                "id": data.get('id'),
                "device_id": data.get('device_id'),
                "name": data.get('name'),
                "current_firmware_version": data.get('current_firmware_version', 'N/A'),  # Dodajemo default vrednost
            })

        formatted_devices.sort(key=lambda x: x['name'])

        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'GET'
            },
            'body': json.dumps(formatted_devices)
        }

    except ClientError as e:
        print(f"boto3 error: {e.response['Error']['Message']}")
        return {'statusCode': 500, 'body': json.dumps({'message': 'Internal Server Error.'})}