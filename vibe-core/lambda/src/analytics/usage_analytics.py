# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Usage Analytics
Analyzes usage patterns and metrics
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
USAGE_METRICS_TABLE = dynamodb.Table('UsageMetrics')


@tracked
def lambda_handler(event, context):
    """
    Analyze usage
    GET /analytics/usage - Get usage analytics
    GET /analytics/usage/{customer_id} - Get company usage
    GET /analytics/usage/app/{appKey} - Get app usage
    """
    print(f"Event: {json.dumps(event, default=decimal_default)}")
    print(f"Context: {context}")
    
    try:
        http_method = event.get('requestContext', {}).get('http', {}).get('method')
        
        if http_method == 'OPTIONS':
            return create_response(200, True)
        
        user_context = extract_user_context(event)
        print(f"User context: {json.dumps(user_context)}")
        
        query_params = event.get('queryStringParameters', {}) or {}

        customer_id = query_params.get('customer_id') or user_context['customer_id']



        # Mock analytics data
        analytics = {
            'total_usage': 10000,
            'active_users': 250,
            'peak_usage_hour': 14,
            'usage_trend': 'increasing'
        }
        
        print(f"Usage analytics calculated for company {customer_id}")
        
        return create_response(200, True, {'analytics': analytics})
        
    except Exception as e:
        print(f"Error analyzing usage: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to analyze usage: {str(e)}")
