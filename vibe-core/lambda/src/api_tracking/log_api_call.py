# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Log API Call — Async Tracking Lambda
Receives fire-and-forget invocations (InvocationType='Event') from other Lambdas
and writes API call tracking records to ApiCallTrackingTable for billing and analytics.

This Lambda is NOT exposed via API Gateway. It is invoked directly by other Lambdas
through the track_api_call() utility function in the UtilsLayer.

Expected payload (passed as the Lambda event):
{
    "company_id": "acme-corp",
    "user_id": "user_123",
    "account_key": "ak_abc",
    "app_key": "app_crm",
    "function_name": "create-user",
    "http_method": "POST",
    "http_path": "/customers/cust-001/users",
    "route_key": "POST /customers/{customer_id}/users",
    "status_code": 201,
    "response_time_ms": 999.9,
    "is_billable": true,
    "request_body_size": 256,
    "timestamp": "2026-03-23T14:30:00.000000Z",
    "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
"""
import json
import boto3
import traceback
import logging
from datetime import datetime, timezone
from decimal import Decimal
from utils.lambda_utils import extract_user_context, decimal_default
import os

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# AWS Clients
dynamodb = boto3.resource('dynamodb')

# Table reference
API_CALL_TRACKING_TABLE = dynamodb.Table('ApiCallTracking')

def decimal_default(obj):
    """JSON serializer for Decimal objects"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError


def lambda_handler(event, context):
    """
    Log a single API call tracking record.
    Invoked asynchronously — no API Gateway, no CORS, no OPTIONS handling.
    """

    print (f'TRACE log_api_call START {str(datetime.utcnow().isoformat())}')
    print(f"Event: {json.dumps(event, default=decimal_default)}")

    try:
        # -----------------------------------------------
        # 1. Extract and validate required fields
        # -----------------------------------------------
        logger.info(f"[LOG_API_CALL.py] LOG_START")
              
        function_name = event.get('function_name')
        ##logger.info(f"LOG_function_name: {function_name}")

        route_key = event.get('route_key')
        ##logger.info(f"LOG_ROUTE KEY — route_key: {route_key}")

        ###
        # Verify JWT and extract caller identity
        ###
        
        user_context = extract_user_context(event)
        ##logger.info(f"LOG_User context: {json.dumps(user_context)}")
        
        if user_context.get('statusCode'):
            logger.warning(f"[AUTH] list_customers blocked — {user_context}")
            return user_context  # 401 — invalid or missing token

 
              
 
        timestamp = str(datetime.utcnow().isoformat())
        request_id = event.get('request_id')


        # -----------------------------------------------
        # 2. Build composite sort key: timestamp#request_id
        # -----------------------------------------------
        timestamp_request_id = f"{timestamp}#{request_id}"

        # -----------------------------------------------
        # 3. Build tracking record
        # -----------------------------------------------
        tracking_record = {
            'customer_id': user_context['customer_id'],
            'timestamp_request_id': timestamp_request_id,
            'user_id': user_context['user_key'],
            'function_name': event.get('function_being_billed', 'unknown'),
            'elapsed_ms' : event.get('elapsed_ms', 'unknownelapsed'),
            'timestamp': timestamp,
            'request_id': request_id,
  
        }

        
        ##logger.info(f'[LOG_API_CALL.py] tracking_record {tracking_record}')
    
 
        # -----------------------------------------------
        # 4. Write to DynamoDB
        # -----------------------------------------------
        API_CALL_TRACKING_TABLE.put_item(Item=tracking_record)
    

        # print(f"Tracked: {tracking_record['function_name']} | "
        #       f"{tracking_record['http_method']} {tracking_record['http_path']} | "
        #       f"company={company_id} | status={tracking_record['status_code']} | "
        #       f"{tracking_record['response_time_ms']}ms")

        logger.info(f"[LOG_API_CALL.py] LOG_END")

        return {
            'success': True,
            'timestamp_request_id': timestamp_request_id
        }

    except Exception as e:
        print(f"Error logging API call: {str(e)}")
        print(traceback.format_exc())
        # Return error but do NOT raise — this is fire-and-forget.
        # Raising would trigger Lambda retry on async invoke, which
        # could cause duplicate records. Log the failure and move on.
        return {
            'success': False,
            'error': str(e)
        }
