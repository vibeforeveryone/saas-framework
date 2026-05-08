# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
List Disputes
Retrieve disputes with filtering and pagination
"""
import json
import boto3
import os
from utils.http_api_compat import normalize_event, get_http_method, get_path_parameter, get_query_parameter, parse_json_body
import logging
from boto3.dynamodb.conditions import Key, Attr
from utils.cors_utils import create_response
from utils.track_api_call import tracked

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
disputes_table = dynamodb.Table('Dispute')

@tracked
def lambda_handler(event, context):
    """
    List disputes with filtering
    
    Query parameters:
    - company_name: Filter by company (required)
    - customer_id: Filter by customer
    - status: Filter by status (open, under_review, won, lost, closed)
    - dispute_type: Filter by type (chargeback, inquiry, fraud)
    - start_date: Start date
    - end_date: End date
    - evidence_required: Filter by evidence requirement
    - limit: Number of results (default 50, max 200)
    """
    # Normalize event for HTTP API compatibility
    event = normalize_event(event)
    

    
    # Extract provider_id and user_id from headers (V2 best practice)
    headers = event.get('headers', {})
    provider_id = (headers.get('X-Provider-Id') or headers.get('x-provider-id') or 
                headers.get('providerId') or 'demo-provider')
    user_id = (headers.get('X-User-Id') or headers.get('x-user-id') or 
            headers.get('userId') or 'demo-user')



    # Fallback to authorizer claims if available
    claims = event.get('requestContext', {}).get('authorizer', {}).get('claims', {})
    if provider_id == 'demo-provider':
        provider_id = claims.get('custom:providerId', provider_id)
        user_id = claims.get('sub', user_id)


    logger.info(f"List disputes request - ProviderId: {provider_id}, UserId: {user_id}")
    logger.info(f"Filtering disputes - company: {company_name}, status: {status}, type: {dispute_type}")
    logger.info(f"Retrieved {total_disputes} disputes for {company_name} by user {user_id} (provider: {provider_id})")

    try:
        # Handle OPTIONS request
        if get_http_method(event) == 'OPTIONS':
            return create_response(200, True)
        
        logger.info(f"List disputes request: {json.dumps(event, default=str)}")
        
        # Get query parameters
        query_params = event.get('queryStringParameters') or {}
        
        company_name = query_params.get('company_name')
        if not company_name:
            return create_response(
                400, False,
                error="company_name query parameter is required"
            )
        
        customer_id = query_params.get('customer_id')
        status = query_params.get('status')
        dispute_type = query_params.get('dispute_type')
        start_date = query_params.get('start_date')
        end_date = query_params.get('end_date')
        evidence_required = query_params.get('evidence_required')
        
        limit = int(query_params.get('limit', 50))
        if limit > 200:
            limit = 200
        
        # Build filter expressions
        filter_expressions = []
        
        # Company filter
        key_condition = Key('company_name').eq(company_name)
        
        if customer_id:
            filter_expressions.append(Attr('customer_id').eq(customer_id))
        
        if status:
            filter_expressions.append(Attr('status').eq(status))
        
        if dispute_type:
            filter_expressions.append(Attr('dispute_type').eq(dispute_type))
        
        if start_date:
            filter_expressions.append(Attr('created_at').gte(start_date))
        
        if end_date:
            filter_expressions.append(Attr('created_at').lte(end_date))
        
        if evidence_required:
            required = evidence_required.lower() == 'true'
            filter_expressions.append(Attr('evidence_required').eq(required))
        
        # Build query parameters
        query_kwargs = {
            'IndexName': 'CustomerIndex',
            'KeyConditionExpression': key_condition,
            'ScanIndexForward': False,  # Descending order
            'Limit': limit
        }
        
        # Add filter expression if any
        if filter_expressions:
            filter_expression = filter_expressions[0]
            for expr in filter_expressions[1:]:
                filter_expression = filter_expression & expr
            query_kwargs['FilterExpression'] = filter_expression
        
        # Execute query
        response = disputes_table.query(**query_kwargs)
        
        items = response.get('Items', [])
        
        # Prepare disputes for response
        disputes = []
        for item in items:
            dispute = {
                'dispute_id': item['dispute_id'],
                'transaction_id': item['transaction_id'],
                'customer_id': item['customer_id'],
                'customer_name': item.get('customer_name'),
                'customer_email': item.get('customer_email'),
                'transaction_amount': float(item['transaction_amount']),
                'disputed_amount': float(item['disputed_amount']),
                'currency': item['currency'],
                'dispute_type': item['dispute_type'],
                'reason_code': item.get('reason_code'),
                'status': item['status'],
                'evidence_required': item.get('evidence_required', False),
                'evidence_submitted': item.get('evidence_submitted', False),
                'created_at': item['created_at'],
                'updated_at': item.get('updated_at')
            }
            
            if item.get('due_date'):
                dispute['due_date'] = item['due_date']
            
            if item.get('resolution'):
                dispute['resolution'] = item['resolution']
                dispute['resolution_date'] = item.get('resolution_date')
            
            disputes.append(dispute)
        
        # Calculate summary
        total_disputes = len(disputes)
        total_amount = sum(d['disputed_amount'] for d in disputes)
        
        status_counts = {}
        type_counts = {}
        
        for d in disputes:
            status_counts[d['status']] = status_counts.get(d['status'], 0) + 1
            type_counts[d['dispute_type']] = type_counts.get(d['dispute_type'], 0) + 1
        
        result_data = {
            'company_name': company_name,
            'disputes': disputes,
            'summary': {
                'total_disputes': total_disputes,
                'total_disputed_amount': round(total_amount, 2),
                'status_breakdown': status_counts,
                'type_breakdown': type_counts
            },
            'filters_applied': {
                'customer_id': customer_id,
                'status': status,
                'dispute_type': dispute_type,
                'start_date': start_date,
                'end_date': end_date
            }
        }
        
        logger.info(f"Retrieved {total_disputes} disputes for {company_name}")
        
        return create_response(200, True, result_data)
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return create_response(500, False, error=f"Failed: {str(e)}")