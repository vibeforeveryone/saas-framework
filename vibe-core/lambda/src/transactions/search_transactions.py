# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Search Transactions
Advanced search across transactions with multiple criteria
"""
import json
import boto3
import os
import logging
from boto3.dynamodb.conditions import Attr
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
    Search transactions with advanced filtering
    
    Query parameters:
    - company_name: Company to search within (required)
    - search_text: Search in customer name, email, or transaction ID
    - customer_email: Exact email match
    - processor_transaction_id: Search by processor transaction ID
    - order_id: Search in metadata.order_id
    - amount_exact: Exact amount match
    - date_range_days: Transactions from last N days
    - limit: Number of results (default 100, max 500)
    """
    try:
        # Handle OPTIONS request
        if event.get('httpMethod') == 'OPTIONS':
            return create_response(200, True)
        
        logger.info(f"Search transactions request: {json.dumps(event, default=str)}")
        
        # Get query parameters
        query_params = event.get('queryStringParameters') or {}
        
        company_name = query_params.get('company_name')
        if not company_name:
            return create_response(
                400, False,
                error="company_name query parameter is required"
            )
        
        search_text = query_params.get('search_text')
        customer_email = query_params.get('customer_email')
        processor_transaction_id = query_params.get('processor_transaction_id')
        order_id = query_params.get('order_id')
        amount_exact = query_params.get('amount_exact')
        date_range_days = query_params.get('date_range_days')
        
        limit = int(query_params.get('limit', 100))
        if limit > 500:
            limit = 500
        
        # Build filter expressions
        filter_expressions = [Attr('company_name').eq(company_name)]
        
        # Search text - search in multiple fields
        if search_text:
            search_lower = search_text.lower()
            text_filters = []
            
            # Search in customer name
            text_filters.append(Attr('customer_name').contains(search_text))
            
            # Search in customer email
            text_filters.append(Attr('customer_email').contains(search_text))
            
            # Search in transaction ID
            text_filters.append(Attr('transaction_id').contains(search_text))
            
            # Combine with OR
            text_filter = text_filters[0]
            for f in text_filters[1:]:
                text_filter = text_filter | f
            
            filter_expressions.append(text_filter)
        
        # Exact email match
        if customer_email:
            filter_expressions.append(Attr('customer_email').eq(customer_email))
        
        # Processor transaction ID
        if processor_transaction_id:
            filter_expressions.append(
                Attr('processor_transaction_id').eq(processor_transaction_id)
            )
        
        # Order ID in metadata
        if order_id:
            filter_expressions.append(
                Attr('metadata.order_id').eq(order_id)
            )
        
        # Exact amount match
        if amount_exact:
            filter_expressions.append(Attr('amount').eq(float(amount_exact)))
        
        # Date range
        if date_range_days:
            from datetime import datetime, timedelta
            cutoff_date = (datetime.utcnow() - timedelta(days=int(date_range_days))).isoformat()
            filter_expressions.append(Attr('created_at').gte(cutoff_date))
        
        # Combine all filter expressions
        filter_expression = filter_expressions[0]
        for expr in filter_expressions[1:]:
            filter_expression = filter_expression & expr
        
        # Execute scan (with filter)
        logger.info(f"Searching transactions for company: {company_name}")
        
        scan_kwargs = {
            'FilterExpression': filter_expression,
            'Limit': limit
        }
        
        response = transactions_table.scan(**scan_kwargs)
        
        items = response.get('Items', [])
        
        # Sort by created_at descending
        items.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        # Convert to response format
        transactions = []
        for item in items:
            transaction = {
                'transaction_id': item['transaction_id'],
                'company_name': item['company_name'],
                'customer_id': item['customer_id'],
                'customer_name': item.get('customer_name'),
                'customer_email': item.get('customer_email'),
                'amount': float(item['amount']),
                'currency': item['currency'],
                'status': item['status'],
                'transaction_type': item['transaction_type'],
                'processor_type': item['processor_type'],
                'processor_transaction_id': item.get('processor_transaction_id'),
                'payment_method_type': item.get('payment_method_type'),
                'created_at': item['created_at'],
                'metadata': item.get('metadata', {})
            }
            
            # Add refund info
            if item.get('refund_status'):
                transaction['refund_status'] = item['refund_status']
                transaction['refunded_amount'] = float(item.get('refunded_amount', 0))
            
            # Add original transaction for refunds
            if item['transaction_type'] == 'refund':
                transaction['original_transaction_id'] = item.get('original_transaction_id')
            
            transactions.append(transaction)
        
        # Calculate summary
        total_found = len(transactions)
        total_amount = sum(t['amount'] for t in transactions)
        
        result_data = {
            'company_name': company_name,
            'search_criteria': {
                'search_text': search_text,
                'customer_email': customer_email,
                'processor_transaction_id': processor_transaction_id,
                'order_id': order_id,
                'amount_exact': amount_exact,
                'date_range_days': date_range_days
            },
            'results': transactions,
            'summary': {
                'total_found': total_found,
                'total_amount': round(total_amount, 2),
                'scanned_count': response.get('ScannedCount', total_found)
            }
        }
        
        logger.info(f"Search found {total_found} transactions")
        
        return create_response(200, True, result_data)
        
    except Exception as e:
        logger.error(f"Error searching transactions: {str(e)}", exc_info=True)
        return create_response(500, False, error=f"Failed to search transactions: {str(e)}")
