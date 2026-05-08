# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
List Users
Lists all users for a customer
Supports AWS API Gateway V2 with header-based authentication
"""
import json
import boto3
import traceback
from datetime import datetime
from decimal import Decimal
from boto3.dynamodb.conditions import Key
from utils.track_api_call import tracked
from utils.lambda_utils import extract_user_context,decimal_default,create_response


dynamodb = boto3.resource('dynamodb')
USER_TABLE = dynamodb.Table('User')



@tracked
def lambda_handler(event, context):
    """
    List all users for a customer
    GET /customers/{customer_id}/users
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
        customer_id = path_params.get('customer_id')
        
        if not customer_id:
            return create_response(400, False, error="Missing customer_id in path")
        
        response = USER_TABLE.query(
            IndexName='customer_id-user_name-index',
            KeyConditionExpression=Key('customer_id').eq(customer_id)
        )
        
        users = response.get('Items', [])
        users = [{k: v for k, v in user.items() if k != 'password_hash'} for user in users]
        users = sorted(users, key=lambda x: x.get('user_name', ''))
        
        print(f"Retrieved {len(users)} users for customer {customer_id}")
        
        return create_response(200, True, {
            'users': users,
            'count': len(users)
        })
        
    except Exception as e:
        print(f"Error listing users: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to list users: {str(e)}")
