# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
List Roles
Returns all system-wide roles. No app_key filter.
GET /roles
"""
import json
import boto3
import traceback
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

        # Scan is appropriate — role list is small (tens of records at most)
        response = ROLE_TABLE.scan()
        roles = response.get('Items', [])

        # Handle DynamoDB pagination (rare but safe)
        while 'LastEvaluatedKey' in response:
            response = ROLE_TABLE.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            roles.extend(response.get('Items', []))

        roles = sorted(roles, key=lambda x: x.get('role_desc', '').lower())

        print(f"Retrieved {len(roles)} system roles")

        return create_response(200, True, {
            'roles': roles,
            'count': len(roles)
        })

    except Exception as e:
        print(f"Error listing roles: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to list roles: {str(e)}")
