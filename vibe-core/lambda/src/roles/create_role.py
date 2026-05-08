# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Create Role
Creates a system-wide role (superuser only). Roles are no longer tied to an application.
POST /roles
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
ROLE_TABLE = dynamodb.Table('Role')


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

        # Superuser guard
        if not user_context.get('is_super_user'):
            return create_response(403, False, error="Superuser access required")

        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})

        if not body.get('role_desc'):
            return create_response(400, False, error="Missing required field: role_desc")

        if len(body['role_desc']) > 30:
            return create_response(400, False, error="role_desc must be 30 characters or less")

        # Enforce uniqueness by role_desc via GSI
        existing = ROLE_TABLE.query(
            IndexName='role_desc-index',
            KeyConditionExpression=Key('role_desc').eq(body['role_desc'])
        )
        if existing.get('Items'):
            return create_response(409, False, error=f"A role named '{body['role_desc']}' already exists")

        role_key = generate_guid()
        current_time = datetime.utcnow().isoformat()

        role = {
            'role_key': role_key,
            'role_desc': body['role_desc'],
            'is_default': body.get('is_default', False),
            'created_at': current_time,
            'modified_at': current_time,
            'created_by': user_context.get('user_id', 'system'),
            'modified_by': user_context.get('user_id', 'system'),
        }

        ROLE_TABLE.put_item(Item=role)
        print(f"Created system role: {role_key} ({body['role_desc']})")

        return create_response(201, True, {
            'role': role,
            'message': 'Role created successfully'
        })

    except json.JSONDecodeError as e:
        return create_response(400, False, error="Invalid JSON in request body")
    except Exception as e:
        print(f"Error creating role: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to create role: {str(e)}")
