# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Create User
Creates a new user for a customer
Supports AWS API Gateway V2 with header-based authentication
"""
import json
import boto3
import traceback
import hashlib
import uuid
from datetime import datetime
from decimal import Decimal
from boto3.dynamodb.conditions import Key
from utils.track_api_call import tracked
from utils.lambda_utils import extract_user_context,decimal_default,create_response


dynamodb = boto3.resource('dynamodb')
USER_TABLE = dynamodb.Table('User')




def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generate_guid():
    return str(uuid.uuid4())

@tracked
def lambda_handler(event, context):
    """
    Create a new user for a customer
    POST /customers/{customer_id}/users
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
        
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        required_fields = ['user_name', 'user_email', 'password']
        missing_fields = [field for field in required_fields if not body.get(field)]
        
        if missing_fields:
            return create_response(400, False, error=f"Missing required fields: {', '.join(missing_fields)}")
        
        if '@' not in body['user_email']:
            return create_response(400, False, error="Invalid email format")
        
        response = USER_TABLE.query(
            IndexName='user_email-index',
            KeyConditionExpression=Key('user_email').eq(body['user_email'])
        )
        
        if response.get('Items'):
            return create_response(400, False, error="Email already exists")
        
        user_key = generate_guid()
        current_time = datetime.utcnow().isoformat()
        
        user = {
            'user_key': user_key,
            'customer_id': customer_id,
            'user_name': body['user_name'],
            'user_email': body['user_email'],
            'password_hash': hash_password(body['password']),
            'status': 'active',
            'is_super_user': body.get('is_super_user', False),
            'created_at': current_time,
            'modified_at': current_time,
            'created_by': user_context['user_id'] or 'system',
            'modified_by': user_context['user_id'] or 'system'
        }
        
        USER_TABLE.put_item(Item=user)
        print(f"Created user: {user_key} for customer {customer_id}")
        
        user_response = {k: v for k, v in user.items() if k != 'password_hash'}
        
        return create_response(201, True, {
            'user': user_response,
            'message': 'User created successfully'
        })
        
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {str(e)}")
        print(traceback.format_exc())
        return create_response(400, False, error="Invalid JSON in request body")
    except Exception as e:
        print(f"Error creating user: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to create user: {str(e)}")
