# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Delete User
Deletes a user
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
USER_TABLE = dynamodb.Table('User')

@tracked
def lambda_handler(event, context):
    """
    Delete a user
    DELETE /customers/{customer_id}/users/{user_key}
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
        
        if not user_key:
            return create_response(400, False, error="Missing user_key in path")
        
        response = USER_TABLE.get_item(Key={'user_key': user_key})
        if 'Item' not in response:
            return create_response(404, False, error=f"User not found: {user_key}")
        
        user = response['Item']
        user_response = {k: v for k, v in user.items() if k != 'password_hash'}
        
        USER_TABLE.delete_item(Key={'user_key': user_key})
        print(f"Deleted user: {user_key}")
        
        return create_response(200, True, {
            'deleted_user': user_response,
            'message': 'User deleted successfully'
        })
        
    except Exception as e:
        print(f"Error deleting user: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to delete user: {str(e)}")
