# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Update Feature
Updates a system-wide feature description (superuser only).
PUT /features/{feature_key}
"""
import json
import boto3
import traceback
from datetime import datetime
from boto3.dynamodb.conditions import Key
from utils.track_api_call import tracked
from utils.lambda_utils import extract_user_context, decimal_default, create_response

dynamodb = boto3.resource('dynamodb')
FEATURE_TABLE = dynamodb.Table('Feature')


@tracked
def lambda_handler(event, context):
    print(f"Event: {json.dumps(event)}")

    try:
        http_method = event.get('requestContext', {}).get('http', {}).get('method')
        if http_method == 'OPTIONS':
            return create_response(200, True)

        user_context = extract_user_context(event)
        print(f"User context: {json.dumps(user_context)}")

        if not user_context.get('is_super_user'):
            return create_response(403, False, error="Superuser access required")

        path_params = event.get('pathParameters', {})
        feature_key = path_params.get('feature_key')
        if not feature_key:
            return create_response(400, False, error="Missing feature_key in path")

        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})

        if not body.get('feature_desc'):
            return create_response(400, False, error="Missing required field: feature_desc")

        if len(body['feature_desc']) > 30:
            return create_response(400, False, error="feature_desc must be 30 characters or less")

        existing = FEATURE_TABLE.get_item(Key={'feature_key': feature_key})
        if 'Item' not in existing:
            return create_response(404, False, error=f"Feature not found: {feature_key}")

        # Name collision check (exclude self)
        name_check = FEATURE_TABLE.query(
            IndexName='feature_desc-index',
            KeyConditionExpression=Key('feature_desc').eq(body['feature_desc'])
        )
        for item in name_check.get('Items', []):
            if item['feature_key'] != feature_key:
                return create_response(409, False, error=f"A feature named '{body['feature_desc']}' already exists")

        response = FEATURE_TABLE.update_item(
            Key={'feature_key': feature_key},
            UpdateExpression="SET feature_desc = :fd, modified_at = :ma, modified_by = :mb",
            ExpressionAttributeValues={
                ':fd': body['feature_desc'],
                ':ma': datetime.utcnow().isoformat(),
                ':mb': user_context.get('user_id', 'system'),
            },
            ReturnValues='ALL_NEW'
        )

        updated_feature = response['Attributes']
        print(f"Updated feature: {feature_key}")

        return create_response(200, True, {
            'feature': updated_feature,
            'message': 'Feature updated successfully'
        })

    except json.JSONDecodeError:
        return create_response(400, False, error="Invalid JSON in request body")
    except Exception as e:
        print(f"Error updating feature: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to update feature: {str(e)}")
