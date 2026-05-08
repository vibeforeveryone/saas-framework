# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Get Customer Transaction History
Retrieve all transactions for a specific customer
"""
import json
import boto3
import os
import logging
from boto3.dynamodb.conditions import Key, Attr
from cors_utils import create_response
from utils.track_api_call import tracked
from utils.lambda_utils import extract_user_context,decimal_default,create_response


logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
transactions_table = dynamodb.Table('TransactionsTable')

@tracked
def lambda_handler(event, context):
    """
    Get customer transaction history
    
    Path parameters:
    - company_name: Company identifier
    - customer_id: Customer identifier
    
    Query parameters:
    - transaction_type: Filter by type (payment, refund)
    - status: Filter by status
    - limit: Number of results (default 50)
    """
    try:
        # Handle OPTIONS request
        if event.get('httpMethod') == 'OPTIONS':
            return create_response(200, True)
        
        logger.info(f"Get customer history request: {json.dumps(event, default=str)}")
        
        # Get path parameters
        path_params = event.get('pathParameters') or {}
        company_name = path_params.get('company_name')
        customer_id = path_params.get('customer_id')
        
        if not company_name or not customer_id:
            return create_response(
                400, False,
                error="company_name and customer_id are required"
            )
        
        # Get query parameters
        query_params = event.get('queryStringParameters') or {}
        transaction_type = query_params.get('transaction_type')
        status = query_params.get('status')
        limit = int(query_params.get('limit', 50))
        
        # Build filter expressions
        filter_expressions = []
        filter_expressions.append(Attr('company_name').eq(company_name))
        filter_expressions.append(Attr('customer_id').eq(customer_id))
        
        if transaction_type:
            filter_expressions.append(Attr('transaction_type').eq(transaction_type))
        
        if status:
            filter_expressions.append(Attr('status').eq(status))
        
        # Combine filters
        filter_expression = filter_expressions[0]
        for expr in filter_expressions[1:]:
            filter_expression = filter_expression & expr
        
        # Query using CustomerIndex (if exists) or scan
        logger.info(f"Querying transactions for customer: {customer_id}")
        
        response = transactions_table.scan(
            FilterExpression=filter_expression,
            Limit=limit
        )
        
        items = response.get('Items', [])
        
        # Sort by created_at descending
        items.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        # Convert to response format
        transactions = []
        for item in items:
            transaction = {
                'transaction_id': item['transaction_id'],
                'amount': float(item['amount']),
                'currency': item['currency'],
                'status': item['status'],
                'transaction_type': item['transaction_type'],
                'processor_type': item['processor_type'],
                'payment_method_type': item.get('payment_method_type'),
                'created_at': item['created_at'],
                'metadata': item.get('metadata', {})
            }
            
            # Add refund info
            if item.get('refund_status'):
                transaction['refund_status'] = item['refund_status']
                transaction['refunded_amount'] = float(item.get('refunded_amount', 0))
            
            # Add void info
            if item['status'] == 'voided':
                transaction['void_reason'] = item.get('void_reason')
            
            # Add original transaction for refunds
            if item['transaction_type'] == 'refund':
                transaction['original_transaction_id'] = item.get('original_transaction_id')
            
            transactions.append(transaction)
        
        # Calculate customer summary
        total_spent = sum(
            t['amount'] for t in transactions
            if t['transaction_type'] == 'payment' and t['status'] == 'completed'
        )
        
        total_refunded = sum(
            t['amount'] for t in transactions
            if t['transaction_type'] == 'refund' and t['status'] == 'completed'
        )
        
        net_spent = total_spent - total_refunded
        
        customer_summary = {
            'customer_id': customer_id,
            'company_name': company_name,
            'total_transactions': len(transactions),
            'total_spent': round(total_spent, 2),
            'total_refunded': round(total_refunded, 2),
            'net_spent': round(net_spent, 2),
            'currency': transactions[0]['currency'] if transactions else 'USD'
        }
        
        # Get customer info from latest transaction
        if transactions:
            latest = items[0]
            customer_summary['customer_name'] = latest.get('customer_name')
            customer_summary['customer_email'] = latest.get('customer_email')
        
        result_data = {
            'customer_summary': customer_summary,
            'transactions': transactions,
            'filters_applied': {
                'transaction_type': transaction_type,
                'status': status
            }
        }
        
        logger.info(f"Retrieved {len(transactions)} transactions for customer {customer_id}")
        
        return create_response(200, True, result_data)
        
    except Exception as e:
        logger.error(f"Error getting customer history: {str(e)}", exc_info=True)
        return create_response(500, False, error=f"Failed to get customer history: {str(e)}")
