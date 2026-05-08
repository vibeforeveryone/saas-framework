# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Create Feature
Creates a system-wide feature (superuser only). Features are no longer tied to an application.
POST /features
"""
import json
import boto3
import traceback
from datetime import datetime
import uuid
from boto3.dynamodb.conditions import Key
from utils.track_api_call import tracked
from utils.lambda_utils import extract_user_context, decimal_default, create_response

dynamodb = boto3.resource('dynamodb')
FEATURE_TABLE = dynamodb.Table('Feature')


def generate_guid():
    return str(uuid.uuid4())


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

        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})

        if not body.get('feature_desc'):
            return create_response(400, False, error="Missing required field: feature_desc")

        if len(body['feature_desc']) > 30:
            return create_response(400, False, error="feature_desc must be 30 characters or less")

        # Uniqueness check via GSI
        existing = FEATURE_TABLE.query(
            IndexName='feature_desc-index',
            KeyConditionExpression=Key('feature_desc').eq(body['feature_desc'])
        )
        if existing.get('Items'):
            return create_response(409, False, error=f"A feature named '{body['feature_desc']}' already exists")

        feature_key = generate_guid()
        current_time = datetime.utcnow().isoformat()

        feature = {
            'feature_key': feature_key,
            'feature_desc': body['feature_desc'],
            'created_at': current_time,
            'modified_at': current_time,
            'created_by': user_context.get('user_id', 'system'),
            'modified_by': user_context.get('user_id', 'system'),
        }

        FEATURE_TABLE.put_item(Item=feature)
        print(f"Created system feature: {feature_key} ({body['feature_desc']})")

        return create_response(201, True, {
            'feature': feature,
            'message': 'Feature created successfully'
        })

    except json.JSONDecodeError:
        return create_response(400, False, error="Invalid JSON in request body")
    except Exception as e:
        print(f"Error creating feature: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to create feature: {str(e)}")
