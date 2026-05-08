# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Get Transaction Details
Retrieve complete details of a specific transaction
"""
import json
import boto3
import os
import logging
from boto3.dynamodb.conditions import Key
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
    Get complete transaction details
    
    Path parameters:
    - transaction_id: Transaction ID to retrieve
    """
    try:
        # Handle OPTIONS request
        if event.get('httpMethod') == 'OPTIONS':
            return create_response(200, True)
        
        logger.info(f"Get transaction request: {json.dumps(event, default=str)}")
        
        # Get path parameters
        path_params = event.get('pathParameters') or {}
        transaction_id = path_params.get('transaction_id')
        
        if not transaction_id:
            return create_response(
                400, False,
                error="transaction_id is required"
            )
        
        # Get transaction from database
        logger.info(f"Retrieving transaction: {transaction_id}")
        response = transactions_table.query(
            KeyConditionExpression=Key('transaction_id').eq(transaction_id)
        )
        
        items = response.get('Items', [])
        if not items:
            return create_response(
                404, False,
                error=f"Transaction not found: {transaction_id}"
            )
        
        transaction = items[0]
        
        # Convert Decimal to float for JSON serialization
        transaction_data = {
            'transaction_id': transaction['transaction_id'],
            'company_name': transaction['company_name'],
            'customer_id': transaction['customer_id'],
            'customer_name': transaction.get('customer_name'),
            'customer_email': transaction.get('customer_email'),
            'amount': float(transaction['amount']),
            'currency': transaction['currency'],
            'status': transaction['status'],
            'transaction_type': transaction['transaction_type'],
            'processor_type': transaction['processor_type'],
            'processor_name': transaction['processor_name'],
            'processor_transaction_id': transaction.get('processor_transaction_id'),
            'payment_method_type': transaction.get('payment_method_type'),
            'created_at': transaction['created_at'],
            'updated_at': transaction.get('updated_at', transaction['created_at']),
            'metadata': transaction.get('metadata', {})
        }
        
        # Add error information if present
        if transaction.get('error_code'):
            transaction_data['error_code'] = transaction['error_code']
            transaction_data['error_details'] = transaction.get('error_details')
        
        # Add refund information if applicable
        if transaction.get('refund_status'):
            transaction_data['refund_status'] = transaction['refund_status']
            transaction_data['refunded_amount'] = float(transaction.get('refunded_amount', 0))
        
        # Add void information if voided
        if transaction['status'] == 'voided':
            transaction_data['void_reason'] = transaction.get('void_reason')
            transaction_data['voided_at'] = transaction.get('voided_at')
        
        # Add original transaction ID for refunds
        if transaction['transaction_type'] == 'refund':
            transaction_data['original_transaction_id'] = transaction.get('original_transaction_id')
            transaction_data['refund_reason'] = transaction.get('refund_reason')
        
        # Add batch information if present
        if transaction.get('metadata', {}).get('batch_id'):
            transaction_data['batch_id'] = transaction['metadata']['batch_id']
        
        # Add raw processor response if present
        if transaction.get('raw_response'):
            transaction_data['raw_response'] = transaction['raw_response']
        
        logger.info(f"Transaction retrieved: {transaction_id}")
        
        return create_response(200, True, transaction_data)
        
    except Exception as e:
        logger.error(f"Error getting transaction: {str(e)}", exc_info=True)
        return create_response(500, False, error=f"Failed to get transaction: {str(e)}")
