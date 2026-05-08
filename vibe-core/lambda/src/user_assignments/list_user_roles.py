# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
List User Roles
Returns all roles assigned to a user, including role_desc names.
GET /customers/{customer_id}/users/{user_key}/roles
"""
import json
import boto3
import traceback
from boto3.dynamodb.conditions import Key
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
        user_key = path_params.get('user_key')

        if not user_key:
            return create_response(400, False, error="Missing user_key in path")

        # Get all role assignments for this user
        response = USER_ROLE_TABLE.query(
            KeyConditionExpression=Key('user_key').eq(user_key)
        )
        assignments = response.get('Items', [])

        if not assignments:
            return create_response(200, True, {'roles': [], 'count': 0})

        # Batch-fetch role details to get role_desc names
        role_keys = [{'role_key': a['role_key']} for a in assignments]

        # DynamoDB batch_get_item supports up to 100 keys
        batch_response = dynamodb.batch_get_item(
            RequestItems={
                'Role': {
                    'Keys': role_keys,
                    'ProjectionExpression': 'role_key, role_desc, is_default'
                }
            }
        )

        role_map = {
            r['role_key']: r
            for r in batch_response.get('Responses', {}).get('Role', [])
        }

        # Merge assignment metadata with role details
        enriched = []
        for assignment in assignments:
            rk = assignment['role_key']
            role_detail = role_map.get(rk, {})
            enriched.append({
                'role_key': rk,
                'role_desc': role_detail.get('role_desc', ''),
                'is_default': role_detail.get('is_default', False),
                'assigned_at': assignment.get('assigned_at', ''),
                'assigned_by': assignment.get('assigned_by', ''),
                'customer_id': assignment.get('customer_id', ''),
            })

        enriched = sorted(enriched, key=lambda x: x.get('role_desc', '').lower())

        print(f"Retrieved {len(enriched)} role assignments for user {user_key}")

        return create_response(200, True, {
            'roles': enriched,
            'count': len(enriched)
        })

    except Exception as e:
        print(f"Error listing user roles: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to list user roles: {str(e)}")
