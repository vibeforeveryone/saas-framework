# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Remove Feature from User
Removes a system-wide feature assignment from a user.
DELETE /customers/{customer_id}/users/{user_key}/features/{feature_key}
"""
import json
import boto3
import traceback
from utils.track_api_call import tracked
from utils.lambda_utils import extract_user_context, decimal_default, create_response

dynamodb = boto3.resource('dynamodb')
USER_FEATURE_TABLE = dynamodb.Table('UserFeature')


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
        feature_key = path_params.get('feature_key')

        if not user_key or not feature_key:
            return create_response(400, False, error="Missing user_key or feature_key in path")

        existing = USER_FEATURE_TABLE.get_item(
            Key={'user_key': user_key, 'feature_key': feature_key}
        )
        if 'Item' not in existing:
            return create_response(404, False, error=f"Feature assignment not found: {user_key}/{feature_key}")

        assignment = existing['Item']

        USER_FEATURE_TABLE.delete_item(
            Key={'user_key': user_key, 'feature_key': feature_key}
        )

        print(f"Removed feature {feature_key} from user {user_key}")

        return create_response(200, True, {
            'removed_assignment': assignment,
            'message': 'Feature removed from user successfully'
        })

    except Exception as e:
        print(f"Error removing feature from user: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to remove feature from user: {str(e)}")
