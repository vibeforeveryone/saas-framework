# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Update Role
Updates a system-wide role description (superuser only).
PUT /roles/{role_key}
"""
import json
import boto3
import traceback
from datetime import datetime
from boto3.dynamodb.conditions import Key
from utils.track_api_call import tracked
from utils.lambda_utils import extract_user_context, decimal_default, create_response

dynamodb = boto3.resource('dynamodb')
ROLE_TABLE = dynamodb.Table('Role')


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

        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})

        if not body.get('role_desc'):
            return create_response(400, False, error="Missing required field: role_desc")

        if len(body['role_desc']) > 30:
            return create_response(400, False, error="role_desc must be 30 characters or less")

        # Confirm role exists
        existing = ROLE_TABLE.get_item(Key={'role_key': role_key})
        if 'Item' not in existing:
            return create_response(404, False, error=f"Role not found: {role_key}")

        # Check for name collision (exclude current record)
        name_check = ROLE_TABLE.query(
            IndexName='role_desc-index',
            KeyConditionExpression=Key('role_desc').eq(body['role_desc'])
        )
        for item in name_check.get('Items', []):
            if item['role_key'] != role_key:
                return create_response(409, False, error=f"A role named '{body['role_desc']}' already exists")

        response = ROLE_TABLE.update_item(
            Key={'role_key': role_key},
            UpdateExpression="SET role_desc = :rd, modified_at = :ma, modified_by = :mb",
            ExpressionAttributeValues={
                ':rd': body['role_desc'],
                ':ma': datetime.utcnow().isoformat(),
                ':mb': user_context.get('user_id', 'system'),
            },
            ReturnValues='ALL_NEW'
        )

        updated_role = response['Attributes']
        print(f"Updated role: {role_key}")

        return create_response(200, True, {
            'role': updated_role,
            'message': 'Role updated successfully'
        })

    except json.JSONDecodeError:
        return create_response(400, False, error="Invalid JSON in request body")
    except Exception as e:
        print(f"Error updating role: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to update role: {str(e)}")
