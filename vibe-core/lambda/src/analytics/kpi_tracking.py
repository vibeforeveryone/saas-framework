# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
KPI Tracking
Tracks and calculates key performance indicators
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
KPI_METRICS_TABLE = dynamodb.Table('KpiMetrics')



@tracked
def lambda_handler(event, context):
    """
    Track KPIs
    GET /kpi - Get current KPIs
    GET /kpi/{metricName}/history - Get KPI history
    """
    ##print(f"Event: {json.dumps(event, default=decimal_default)}")
    ##print(f"Context: {context}")
    
    try:
        http_method = event.get('requestContext', {}).get('http', {}).get('method')
        
        if http_method == 'OPTIONS':
            return create_response(200, True)
        
        user_context = extract_user_context(event)
        print(f"User context: {json.dumps(user_context)}")
        
        query_params = event.get('queryStringParameters', {}) or {}
        customer_id = query_params.get('customer_id') or user_context['customer_id']
        
        # Mock KPI data
        kpis = {
            'total_revenue': 100000,
            'active_users': 500,
            'conversion_rate': 0.15,
            'churn_rate': 0.05
        }
        
        print(f"KPIs calculated for company {customer_id}")
        
        return create_response(200, True, {'kpis': kpis})
        
    except Exception as e:
        print(f"Error tracking KPIs: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to track KPIs: {str(e)}")
