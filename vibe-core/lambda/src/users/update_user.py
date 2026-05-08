# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Update User
Updates an existing user
Supports AWS API Gateway V2 with header-based authentication
"""
import json
import boto3
import traceback
import hashlib
from datetime import datetime
from decimal import Decimal
from utils.track_api_call import tracked
from utils.lambda_utils import extract_user_context,decimal_default,create_response


dynamodb = boto3.resource('dynamodb')
USER_TABLE = dynamodb.Table('User')





def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

@tracked
def lambda_handler(event, context):
    """
    Update an existing user
    PUT /customers/{customer_id}/users/{user_key}
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
        
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        response = USER_TABLE.get_item(Key={'user_key': user_key})
        if 'Item' not in response:
            return create_response(404, False, error=f"User not found: {user_key}")
        
        update_expression = "SET modified_at = :modified_at, modified_by = :modified_by"
        expression_values = {
            ':modified_at': datetime.utcnow().isoformat(),
            ':modified_by': user_context['user_id'] or 'system'
        }
        
        if 'user_name' in body:
            update_expression += ", user_name = :user_name"
            expression_values[':user_name'] = body['user_name']
        
        if 'user_email' in body:
            if '@' not in body['user_email']:
                return create_response(400, False, error="Invalid email format")
            update_expression += ", user_email = :user_email"
            expression_values[':user_email'] = body['user_email']
        
        if 'password' in body:
            update_expression += ", password_hash = :password_hash"
            expression_values[':password_hash'] = hash_password(body['password'])
        
        if 'is_super_user' in body:
            update_expression += ", is_super_user = :is_super_user"
            expression_values[':is_super_user'] = bool(body['is_super_user'])
        
        response = USER_TABLE.update_item(
            Key={'user_key': user_key},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values,
            ReturnValues='ALL_NEW'
        )
        
        updated_user = response['Attributes']
        user_response = {k: v for k, v in updated_user.items() if k != 'password_hash'}
        
        print(f"Updated user: {user_key}")
        
        return create_response(200, True, {
            'user': user_response,
            'message': 'User updated successfully'
        })
        
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {str(e)}")
        print(traceback.format_exc())
        return create_response(400, False, error="Invalid JSON in request body")
    except Exception as e:
        print(f"Error updating user: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to update user: {str(e)}")
