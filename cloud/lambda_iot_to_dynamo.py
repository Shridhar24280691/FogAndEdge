import json
from decimal import Decimal
from datetime import datetime
import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("SmartHomeMosquittoReadings")

def normalize(item):
    out = {}
    for k, v in item.items():
        if isinstance(v, float):
            out[k] = Decimal(str(v))
        elif isinstance(v, dict):
            out[k] = {ik: normalize(iv) if isinstance(iv, dict) else Decimal(str(iv)) if isinstance(iv, float) else iv for ik, iv in v.items()}
        elif isinstance(v, list):
            out[k] = [Decimal(str(x)) if isinstance(x, float) else x for x in v]
        else:
            out[k] = v
    return out

def lambda_handler(event, context):
    payload = event

    if "timestamp" not in payload:
        payload["timestamp"] = datetime.utcnow().isoformat() + "Z"

    item = normalize(payload)
    table.put_item(Item=item)

    return {"statusCode": 200, "body": json.dumps({"ok": True})}
