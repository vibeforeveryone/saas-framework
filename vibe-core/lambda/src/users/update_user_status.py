# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Update User Status
Updates user status (active/suspended/inactive)
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
    Update user status
    PUT /customers/{customer_id}/users/{user_key}/status
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
        
        if 'status' not in body:
            return create_response(400, False, error="Missing required field: status")
        
        status = body['status']
        valid_statuses = ['active', 'suspended', 'inactive']
        
        if status not in valid_statuses:
            return create_response(400, False, error=f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        
        response = USER_TABLE.get_item(Key={'user_key': user_key})
        if 'Item' not in response:
            return create_response(404, False, error=f"User not found: {user_key}")
        
        update_expression = "SET #status = :status, modified_at = :modified_at, modified_by = :modified_by"
        expression_names = {'#status': 'status'}
        expression_values = {
            ':status': status,
            ':modified_at': datetime.utcnow().isoformat(),
            ':modified_by': user_context['user_id'] or 'system'
        }
        
        response = USER_TABLE.update_item(
            Key={'user_key': user_key},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_names,
            ExpressionAttributeValues=expression_values,
            ReturnValues='ALL_NEW'
        )
        
        updated_user = response['Attributes']
        user_response = {k: v for k, v in updated_user.items() if k != 'password_hash'}
        
        print(f"Updated user status: {user_key} -> {status}")
        
        return create_response(200, True, {
            'user': user_response,
            'message': f'User status updated to {status}'
        })
        
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {str(e)}")
        print(traceback.format_exc())
        return create_response(400, False, error="Invalid JSON in request body")
    except Exception as e:
        print(f"Error updating user status: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to update user status: {str(e)}")
