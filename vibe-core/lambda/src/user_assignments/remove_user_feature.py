# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Remove Feature from User
Remove a feature assignment from a user
Supports AWS API Gateway V2 with header-based authentication
"""
import json
import boto3
import traceback
from datetime import datetime
from decimal import Decimal
from utils.track_api_call import tracked
from utils.lambda_utils import extract_user_context,decimal_default,create_response


dynamodb = boto3.resource('dynamodb')
USER_APP_FEATURE_TABLE = dynamodb.Table('UserAppFeature')



@tracked
def lambda_handler(event, context):
    """
    Remove a feature assignment from a user
    DELETE /customers/{customer_id}/users/{user_key}/features/{app_feature_key}
    """
    print(f"Event: {json.dumps(event, default=decimal_default)}")
    print(f"Context: {context}")
    
    try:
        http_method = event.get('requestContext', {}).get('http', {}).get('method')
        
        if http_method == 'OPTIONS':
            return create_response(200, True)
        
        user_context = extract_user_context(event)
        print(f"User context: {json.dumps(user_context)}")
        
        path_params = event.get('pathParameters', {})
        user_key = path_params.get('user_key')
        app_feature_key = path_params.get('app_feature_key')
        
        if not user_key or not app_feature_key:
            return create_response(400, False, error="Missing user_key or app_feature_key in path")
        
        # Check if assignment exists
        response = USER_APP_FEATURE_TABLE.get_item(
            Key={'user_key': user_key, 'app_feature_key': app_feature_key}
        )
        
        if 'Item' not in response:
            return create_response(404, False, error=f"Feature assignment not found: {user_key}/{app_feature_key}")
        
        assignment = response['Item']
        
        USER_APP_FEATURE_TABLE.delete_item(
            Key={'user_key': user_key, 'app_feature_key': app_feature_key}
        )
        
        print(f"Removed feature {app_feature_key} from user {user_key}")
        
        return create_response(200, True, {
            'removed_assignment': assignment,
            'message': 'Feature removed from user successfully'
        })
        
    except Exception as e:
        print(f"Error removing feature from user: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to remove feature from user: {str(e)}")
