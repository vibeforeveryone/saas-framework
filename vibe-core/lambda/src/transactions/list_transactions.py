# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
List Transactions
Retrieve transaction history with filtering and pagination
Supports AWS API Gateway V2 with header-based authentication
"""
import json
import boto3
import traceback
from datetime import datetime, timedelta
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr
from utils.track_api_call import tracked
from utils.lambda_utils import extract_user_context,decimal_default,create_response



# AWS Clients
dynamodb = boto3.resource('dynamodb')

# Hardcoded table name
TRANSACTIONS_TABLE = dynamodb.Table('PaymentTransaction')


   
   
@tracked
def lambda_handler(event, context):
    """
    List transactions with filtering and pagination
    GET /customers/{customer_id}/transactions
    
    Query parameters:
    - customer_id: Filter by customer
    - status: Filter by status (completed, failed, pending, voided)
    - transaction_type: Filter by type (payment, refund)
    - start_date: Start date (ISO format)
    - end_date: End date (ISO format)
    - min_amount: Minimum amount
    - max_amount: Maximum amount
    - limit: Number of results (default 50, max 200)
    """
    
    # Log comprehensive request context
    print(f"Event: {json.dumps(event, default=decimal_default)}")
    print(f"Context: {context}")
    
    try:
        # Get HTTP method
        http_method = event.get('requestContext', {}).get('http', {}).get('method')
        
        # Handle OPTIONS preflight request
        if http_method == 'OPTIONS':
            return create_response(200, True)
        
        # Extract user context from headers
        user_context = extract_user_context(event)
        print(f"User context: {json.dumps(user_context)}")
        
        # Get path parameters
        path_params = event.get('pathParameters', {})
        customer_id = path_params.get('customer_id') or user_context['customer_id']
        
        if not customer_id:
            return create_response(400, False, error="customer_id is required")
        
        # Get query parameters
        query_params = event.get('queryStringParameters', {}) or {}
        
        status = query_params.get('status')
        transaction_type = query_params.get('transaction_type')
        start_date = query_params.get('start_date')
        end_date = query_params.get('end_date')
        min_amount = query_params.get('min_amount')
        max_amount = query_params.get('max_amount')
        
        # Pagination
        limit = int(query_params.get('limit', 50))
        if limit > 200:
            limit = 200
        
        # Build query using customer_id-created_at-index
        print(f"Querying transactions for customer: {customer_id}")
        
        query_kwargs = {
            'IndexName': 'customer_id-created_at-index',
            'KeyConditionExpression': Key('customer_id').eq(customer_id),
            'ScanIndexForward': False,  # Descending order (newest first)
            'Limit': limit
        }
        
        # Build filter expressions
        filter_expressions = []
        
        # Date range filter
        if start_date and end_date:
            query_kwargs['KeyConditionExpression'] = (
                Key('customer_id').eq(customer_id) & 
                Key('created_at').between(start_date, end_date)
            )
        elif start_date:
            query_kwargs['KeyConditionExpression'] = (
                Key('customer_id').eq(customer_id) & 
                Key('created_at').gte(start_date)
            )
        elif end_date:
            query_kwargs['KeyConditionExpression'] = (
                Key('customer_id').eq(customer_id) &
                Key('created_at').lte(end_date)
            )
        
        # Status filter
        if status:
            filter_expressions.append(Attr('status').eq(status))
        
        # Transaction type filter
        if transaction_type:
            filter_expressions.append(Attr('transaction_type').eq(transaction_type))
        
        # Amount range filters
        if min_amount:
            filter_expressions.append(Attr('amount').gte(Decimal(min_amount)))
        
        if max_amount:
            filter_expressions.append(Attr('amount').lte(Decimal(max_amount)))
        
        # Combine filter expressions
        if filter_expressions:
            filter_expression = filter_expressions[0]
            for expr in filter_expressions[1:]:
                filter_expression = filter_expression & expr
            query_kwargs['FilterExpression'] = filter_expression
        
        # Execute query
        response = TRANSACTIONS_TABLE.query(**query_kwargs)
        
        items = response.get('Items', [])
        
        # Convert to response format
        transactions = []
        for item in items:
            transaction = {
                'transaction_id': item['transaction_id'],
                'customer_id': item['customer_id'],
                'amount': float(item['amount']),
                'currency': item['currency'],
                'status': item['status'],
                'transaction_type': item['transaction_type'],
                'processor_type': item.get('processor_type'),
                'processor_transaction_id': item.get('processor_transaction_id'),
                'payment_method_type': item.get('payment_method_type'),
                'customer_email': item.get('customer_email'),
                'customer_name': item.get('customer_name'),
                'created_at': item['created_at']
            }
            
            # Add refund info if applicable
            if item.get('refund_status'):
                transaction['refund_status'] = item['refund_status']
                transaction['refunded_amount'] = float(item.get('refunded_amount', 0))
            
            # Add metadata if present
            if item.get('metadata'):
                transaction['metadata'] = item['metadata']
            
            transactions.append(transaction)
        
        # Calculate summary
        total_returned = len(transactions)
        total_amount = sum(t['amount'] for t in transactions)
        
        summary = {
            'total_returned': total_returned,
            'total_amount': round(total_amount, 2),
            'currency': transactions[0]['currency'] if transactions else 'USD'
        }
        
        # Count by status
        status_counts = {}
        for t in transactions:
            status_counts[t['status']] = status_counts.get(t['status'], 0) + 1
        summary['status_breakdown'] = status_counts
        
        result_data = {
            'customer_id': customer_id,
            'transactions': transactions,
            'summary': summary,
            'pagination': {
                'limit': limit,
                'returned_count': total_returned,
                'has_more': 'LastEvaluatedKey' in response
            },
            'filters_applied': {
                'customer_id': customer_id,
                'status': status,
                'transaction_type': transaction_type,
                'start_date': start_date,
                'end_date': end_date,
                'min_amount': min_amount,
                'max_amount': max_amount
            }
        }
        
        # Add pagination token if more results available
        if 'LastEvaluatedKey' in response:
            result_data['pagination']['last_evaluated_key'] = json.dumps(
                response['LastEvaluatedKey'], default=decimal_default
            )
        
        print(f"Retrieved {total_returned} transactions for {customer_id}")
        
        return create_response(200, True, result_data)
        
    except Exception as e:
        print(f"Error listing transactions: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to list transactions: {str(e)}")
