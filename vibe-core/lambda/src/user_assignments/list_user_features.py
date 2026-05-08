# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
List User Feature Assignments
Get all feature assignments for a user
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
USER_APP_FEATURE_TABLE = dynamodb.Table('UserAppFeature')


@tracked
def lambda_handler(event, context):
    """
    List all feature assignments for a user
    GET /customers/{customer_id}/users/{user_key}/features
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
        
        # Query by user_key (partition key)
        response = USER_APP_FEATURE_TABLE.query(
            KeyConditionExpression=Key('user_key').eq(user_key)
        )
        
        features = response.get('Items', [])
        features = sorted(features, key=lambda x: x.get('app_feature_key', ''))
        
        print(f"Retrieved {len(features)} feature assignments for user {user_key}")
        
        return create_response(200, True, {
            'features': features,
            'count': len(features)
        })
        
    except Exception as e:
        print(f"Error listing user features: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to list user features: {str(e)}")
