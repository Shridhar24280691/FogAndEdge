import os
import json
import boto3
from boto3.dynamodb.conditions import Key

TABLE_NAME = os.environ.get("READINGS_TABLE", "SmartHomeMosquittoReadings")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)

def lambda_handler(event, context):
    params = event.get("queryStringParameters") or {}
    device_ids_param = params.get("deviceIds", "")
    limit = int(params.get("limit", "100"))

    device_ids = [d.strip() for d in device_ids_param.split(",") if d.strip()]
    all_items = []

    for device_id in device_ids:
        response = table.query(
            KeyConditionExpression=Key("deviceId").eq(device_id),
            ScanIndexForward=True,
            Limit=limit
        )
        all_items.extend(response.get("Items", []))

    return {
        "statusCode": 200,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "application/json"
        },
        "body": json.dumps(all_items, default=str)
    }
