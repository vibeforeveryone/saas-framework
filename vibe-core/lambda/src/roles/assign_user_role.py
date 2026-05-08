# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Assign Role to User
Assigns a system-wide role to a user (admin or superuser only).
POST /customers/{customer_id}/users/{user_key}/roles
Body: { "role_key": "..." }
"""
import json
import boto3
import traceback
from datetime import datetime
from utils.track_api_call import tracked
from utils.lambda_utils import extract_user_context, decimal_default, create_response

dynamodb = boto3.resource('dynamodb')
USER_ROLE_TABLE = dynamodb.Table('UserRole')
ROLE_TABLE = dynamodb.Table('Role')


@tracked
def lambda_handler(event, context):
    print(f"Event: {json.dumps(event, default=decimal_default)}")

    try:
        http_method = event.get('requestContext', {}).get('http', {}).get('method')
        if http_method == 'OPTIONS':
            return create_response(200, True)

        user_context = extract_user_context(event)
        print(f"User context: {json.dumps(user_context)}")

        path_params = event.get('pathParameters', {})
        customer_id = path_params.get('customer_id') or user_context.get('customer_id')
        user_key = path_params.get('user_key')

        if not user_key:
            return create_response(400, False, error="Missing user_key in path")

        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})

        role_key = body.get('role_key')
        if not role_key:
            return create_response(400, False, error="Missing required field: role_key")

        # Confirm the role exists in the system
        role_item = ROLE_TABLE.get_item(Key={'role_key': role_key})
        if 'Item' not in role_item:
            return create_response(404, False, error=f"Role not found: {role_key}")

        # Check if already assigned
        existing = USER_ROLE_TABLE.get_item(
            Key={'user_key': user_key, 'role_key': role_key}
        )
        if 'Item' in existing:
            return create_response(400, False, error="Role is already assigned to this user")

        current_time = datetime.utcnow().isoformat()

        assignment = {
            'user_key': user_key,
            'role_key': role_key,
            'customer_id': customer_id,
            'assigned_at': current_time,
            'assigned_by': user_context.get('user_id', 'system'),
        }

        USER_ROLE_TABLE.put_item(Item=assignment)
        print(f"Assigned role {role_key} to user {user_key}")

        return create_response(201, True, {
            'assignment': assignment,
            'message': 'Role assigned to user successfully'
        })

    except json.JSONDecodeError:
        return create_response(400, False, error="Invalid JSON in request body")
    except Exception as e:
        print(f"Error assigning role to user: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to assign role to user: {str(e)}")
