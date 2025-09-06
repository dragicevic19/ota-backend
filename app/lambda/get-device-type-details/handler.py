import os
import json
import boto3
from botocore.exceptions import ClientError

TABLE_NAME = os.environ.get('TABLE_NAME')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(TABLE_NAME)


def main(event, context):
    try:
        device_type_id = event['pathParameters']['deviceTypeId']
        pk = f"DEVICE_TYPE#{device_type_id}"

        response = table.query(
            KeyConditionExpression='PK = :pk',
            ExpressionAttributeValues={':pk': pk}
        )
        items = response.get('Items', [])

        if not items:
            return {'statusCode': 404, 'body': json.dumps({'message': 'Device type not found.'})}

        active_deployments = {}
        all_versions = []

        for item in items:
            sk = item.get('SK', '')
            if sk.startswith('GROUP#'):
                group_name = sk.split('#', 1)[1]
                active_deployments[group_name] = item
            elif sk.startswith('VERSION#'):
                item.pop('PK', None)
                item.pop('SK', None)
                all_versions.append(item)

        all_versions.sort(key=lambda x: x.get('version_number', ''), reverse=True)

        result = {
            "id": device_type_id,
            "name": device_type_id.replace('-', ' ').title(),
            "active_deployments": active_deployments,
            "firmware_versions": all_versions
        }

        return {
            'statusCode': 200,
            'headers': {'Access-Control-Allow-Origin': '*'},  # CORS
            'body': json.dumps(result)
        }

    except KeyError:
        return {'statusCode': 400, 'body': json.dumps({'message': 'Missing deviceTypeId in path.'})}
    except ClientError as e:
        print(e.response['Error']['Message'])
        return {'statusCode': 500, 'body': json.dumps({'message': 'Error accessing database.'})}