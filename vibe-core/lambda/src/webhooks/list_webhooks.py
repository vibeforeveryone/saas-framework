# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
List Webhooks
Retrieve webhook history with filtering
Supports AWS API Gateway V2 with header-based authentication
"""
import json
import boto3
import traceback
from datetime import datetime
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr
from utils.track_api_call import tracked
from utils.lambda_utils import extract_user_context,decimal_default,create_response


dynamodb = boto3.resource('dynamodb')
WEBHOOKS_TABLE = dynamodb.Table('WebhookEvent')


@tracked
def lambda_handler(event, context):
    """
    List webhooks with filtering
    GET /webhooks
    
    Query parameters:
    - customer_id: Filter by customer
    - processor_type: Filter by processor
    - status: Filter by status (pending, processed, failed)
    - start_date: Start date (ISO format)
    - end_date: End date (ISO format)
    - limit: Number of results (default 50, max 200)
    """
    print(f"Event: {json.dumps(event, default=decimal_default)}")
    print(f"Context: {context}")
    
    try:
        http_method = event.get('requestContext', {}).get('http', {}).get('method')
        
        if http_method == 'OPTIONS':
            return create_response(200, True)
        
        user_context = extract_user_context(event)
        print(f"User context: {json.dumps(user_context)}")
        
        # Get query parameters
        query_params = event.get('queryStringParameters', {}) or {}
        
        customer_id = query_params.get('customer_id') or user_context['customer_id']
        processor_type = query_params.get('processor_type')
        status = query_params.get('status')
        start_date = query_params.get('start_date')
        end_date = query_params.get('end_date')
        
        limit = int(query_params.get('limit', 50))
        if limit > 200:
            limit = 200
        
        # Build filter expressions
        filter_expressions = []
        
        if processor_type:
            filter_expressions.append(Attr('processor_type').eq(processor_type))
        
        if status:
            filter_expressions.append(Attr('status').eq(status))
        
        if start_date:
            filter_expressions.append(Attr('created_at').gte(start_date))
        
        if end_date:
            filter_expressions.append(Attr('created_at').lte(end_date))
        
        # Build query/scan parameters
        if customer_id:
            # Query using customer_id-created_at-index
            query_kwargs = {
                'IndexName': 'customer_id-created_at-index',
                'KeyConditionExpression': Key('customer_id').eq(customer_id),
                'ScanIndexForward': False,
                'Limit': limit
            }
            
            if filter_expressions:
                filter_expression = filter_expressions[0]
                for expr in filter_expressions[1:]:
                    filter_expression = filter_expression & expr
                query_kwargs['FilterExpression'] = filter_expression
            
            response = WEBHOOKS_TABLE.query(**query_kwargs)
        else:
            # Scan entire table
            scan_kwargs = {'Limit': limit}
            
            if filter_expressions:
                filter_expression = filter_expressions[0]
                for expr in filter_expressions[1:]:
                    filter_expression = filter_expression & expr
                scan_kwargs['FilterExpression'] = filter_expression
            
            response = WEBHOOKS_TABLE.scan(**scan_kwargs)
        
        items = response.get('Items', [])
        items.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        # Prepare response
        webhooks = []
        status_counts = {}
        
        for item in items:
            webhook = {
                'webhook_key': item['webhook_key'],
                'processor_type': item['processor_type'],
                'status': item['status'],
                'created_at': item['created_at'],
                'signature_verified': item.get('signature_verified'),
                'retry_count': item.get('retry_count', 0)
            }
            
            if item.get('processed_at'):
                webhook['processed_at'] = item['processed_at']
            
            webhooks.append(webhook)
            
            s = item['status']
            status_counts[s] = status_counts.get(s, 0) + 1
        
        result_data = {
            'webhooks': webhooks,
            'summary': {
                'total_returned': len(webhooks),
                'status_breakdown': status_counts
            },
            'filters_applied': {
                'customer_id': customer_id,
                'processor_type': processor_type,
                'status': status,
                'start_date': start_date,
                'end_date': end_date
            }
        }
        
        print(f"Retrieved {len(webhooks)} webhooks")
        
        return create_response(200, True, result_data)
        
    except Exception as e:
        print(f"Error listing webhooks: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to list webhooks: {str(e)}")
