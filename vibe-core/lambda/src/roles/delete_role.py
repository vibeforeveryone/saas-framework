# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Delete Role
Deletes a system-wide role (superuser only).
Blocked if the role is marked is_default or is currently assigned to any user.
DELETE /roles/{role_key}
"""
import json
import boto3
import traceback
from boto3.dynamodb.conditions import Key
from utils.track_api_call import tracked
from utils.lambda_utils import extract_user_context, decimal_default, create_response

dynamodb = boto3.resource('dynamodb')
ROLE_TABLE = dynamodb.Table('Role')
USER_ROLE_TABLE = dynamodb.Table('UserRole')


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
        role_key = path_params.get('role_key')
        if not role_key:
            return create_response(400, False, error="Missing role_key in path")

        # Confirm role exists
        existing = ROLE_TABLE.get_item(Key={'role_key': role_key})
        if 'Item' not in existing:
            return create_response(404, False, error=f"Role not found: {role_key}")

        role = existing['Item']

        # Block deletion of default roles
        if role.get('is_default'):
            return create_response(400, False, error=f"Cannot delete default role '{role.get('role_desc')}'")

        # Block deletion if role is assigned to any user
        assigned = USER_ROLE_TABLE.query(
            IndexName='role_key-index',
            KeyConditionExpression=Key('role_key').eq(role_key),
            Limit=1
        )
        if assigned.get('Items'):
            return create_response(400, False,
                error="Cannot delete role that is currently assigned to users. Remove all assignments first.")

        ROLE_TABLE.delete_item(Key={'role_key': role_key})
        print(f"Deleted role: {role_key}")

        return create_response(200, True, {
            'deleted_role': role,
            'message': 'Role deleted successfully'
        })

    except Exception as e:
        print(f"Error deleting role: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to delete role: {str(e)}")
