# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Assign Feature to User
Assign a feature to a user for a specific application
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
    Assign a feature to a user for a specific application
    POST /customers/{customer_id}/users/{user_key}/features
    
    Expected payload:
    {
        "app_key": "app_crm",
        "feature_key": "feature_reports"
    }
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
        
        required_fields = ['app_key', 'feature_key']
        missing_fields = [field for field in required_fields if not body.get(field)]
        
        if missing_fields:
            return create_response(400, False, error=f"Missing required fields: {', '.join(missing_fields)}")
        
        app_key = body['app_key']
        feature_key = body['feature_key']
        app_feature_key = f"{app_key}#{feature_key}"
        
        # Check if assignment already exists
        response = USER_APP_FEATURE_TABLE.get_item(
            Key={'user_key': user_key, 'app_feature_key': app_feature_key}
        )
        
        if 'Item' in response:
            return create_response(400, False, error="Feature already assigned to this user")
        
        current_time = datetime.utcnow().isoformat()
        
        assignment = {
            'user_key': user_key,
            'app_feature_key': app_feature_key,
            'app_key': app_key,
            'feature_key': feature_key,
            'assigned_at': current_time,
            'created_at': current_time,
            'modified_at': current_time,
            'created_by': user_context['user_id'] or body.get('created_by', 'system'),
            'modified_by': user_context['user_id'] or body.get('modified_by', 'system')
        }
        
        USER_APP_FEATURE_TABLE.put_item(Item=assignment)
        
        print(f"Assigned feature {feature_key} to user {user_key} in app {app_key}")
        
        return create_response(201, True, {
            'assignment': assignment,
            'message': 'Feature assigned to user successfully'
        })
        
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {str(e)}")
        print(traceback.format_exc())
        return create_response(400, False, error="Invalid JSON in request body")
    except Exception as e:
        print(f"Error assigning feature to user: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to assign feature to user: {str(e)}")
