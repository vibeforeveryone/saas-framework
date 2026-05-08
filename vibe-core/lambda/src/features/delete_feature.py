# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Delete Feature
Deletes a system-wide feature (superuser only).
Blocked if the feature is currently assigned to any user.
DELETE /features/{feature_key}
"""
import json
import boto3
import traceback
from boto3.dynamodb.conditions import Key
from utils.track_api_call import tracked
from utils.lambda_utils import extract_user_context, decimal_default, create_response

dynamodb = boto3.resource('dynamodb')
FEATURE_TABLE = dynamodb.Table('Feature')
USER_FEATURE_TABLE = dynamodb.Table('UserFeature')


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

        existing = FEATURE_TABLE.get_item(Key={'feature_key': feature_key})
        if 'Item' not in existing:
            return create_response(404, False, error=f"Feature not found: {feature_key}")

        feature = existing['Item']

        # Block deletion if assigned to any user
        assigned = USER_FEATURE_TABLE.query(
            IndexName='feature_key-index',
            KeyConditionExpression=Key('feature_key').eq(feature_key),
            Limit=1
        )
        if assigned.get('Items'):
            return create_response(400, False,
                error="Cannot delete feature that is currently assigned to users. Remove all assignments first.")

        FEATURE_TABLE.delete_item(Key={'feature_key': feature_key})
        print(f"Deleted feature: {feature_key}")

        return create_response(200, True, {
            'deleted_feature': feature,
            'message': 'Feature deleted successfully'
        })

    except Exception as e:
        print(f"Error deleting feature: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to delete feature: {str(e)}")
