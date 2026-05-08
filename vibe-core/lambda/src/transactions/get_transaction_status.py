# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Get Transaction Status
Retrieve current status of a transaction from both database and payment processor
"""
import json
import boto3
import os
import logging
from boto3.dynamodb.conditions import Key
from cors_utils import create_response
from payment.processor_factory import ProcessorFactory
from payment_processors.get_processor_config import get_active_processor_config
from utils.track_api_call import tracked
from utils.lambda_utils import extract_user_context,decimal_default,create_response


logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
transactions_table = dynamodb.Table('TransactionsTable')

@tracked
def lambda_handler(event, context):
    """
    Get transaction status
    
    Path parameters:
    - transaction_id: Transaction ID to check
    
    Query parameters:
    - check_processor: If 'true', also check status with payment processor
    - include_details: If 'true', include full transaction details
    """
    try:
        # Handle OPTIONS request
        if event.get('httpMethod') == 'OPTIONS':
            return create_response(200, True)
        
        logger.info(f"Get transaction status request: {json.dumps(event, default=str)}")
        
        # Get path parameters
        path_params = event.get('pathParameters') or {}
        transaction_id = path_params.get('transaction_id')
        
        if not transaction_id:
            return create_response(
                400, False,
                error="transaction_id is required"
            )
        
        # Get query parameters
        query_params = event.get('queryStringParameters') or {}
        check_processor = query_params.get('check_processor', 'false').lower() == 'true'
        include_details = query_params.get('include_details', 'false').lower() == 'true'
        
        # Get transaction from database
        logger.info(f"Looking up transaction: {transaction_id}")
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
        
        # Prepare basic status response
        status_data = {
            'transaction_id': transaction_id,
            'status': transaction['status'],
            'transaction_type': transaction['transaction_type'],
            'amount': float(transaction['amount']),
            'currency': transaction['currency'],
            'created_at': transaction['created_at'],
            'updated_at': transaction.get('updated_at', transaction['created_at'])
        }
        
        # Add refund information if applicable
        if transaction.get('refund_status'):
            status_data['refund_status'] = transaction['refund_status']
            status_data['refunded_amount'] = float(transaction.get('refunded_amount', 0))
        
        # Add processor status if requested
        processor_status = None
        if check_processor and transaction.get('processor_transaction_id'):
            try:
                company_name = transaction['company_name']
                processor_config = get_active_processor_config(company_name)
                
                if processor_config:
                    processor = ProcessorFactory.create_from_config_record(processor_config)
                    
                    logger.info(f"Checking processor status for: {transaction['processor_transaction_id']}")
                    processor_response = processor.get_transaction_status(
                        transaction['processor_transaction_id']
                    )
                    
                    if processor_response.success:
                        processor_status = {
                            'processor_status': processor_response.status,
                            'processor_message': processor_response.message,
                            'checked_at': processor_response.timestamp
                        }
                        
                        # Update database if processor status differs
                        if processor_response.status != transaction['status']:
                            logger.warning(
                                f"Status mismatch - DB: {transaction['status']}, "
                                f"Processor: {processor_response.status}"
                            )
                            processor_status['status_mismatch'] = True
                    else:
                        processor_status = {
                            'error': 'Failed to retrieve processor status',
                            'error_details': processor_response.error_details
                        }
                else:
                    processor_status = {
                        'error': 'No active processor configured'
                    }
                    
            except Exception as e:
                logger.error(f"Error checking processor status: {str(e)}")
                processor_status = {
                    'error': 'Failed to check processor status',
                    'error_details': str(e)
                }
        
        if processor_status:
            status_data['processor_status'] = processor_status
        
        # Include full details if requested
        if include_details:
            details = {
                'company_name': transaction['company_name'],
                'customer_id': transaction['customer_id'],
                'customer_email': transaction.get('customer_email'),
                'customer_name': transaction.get('customer_name'),
                'payment_method_type': transaction.get('payment_method_type'),
                'processor_type': transaction['processor_type'],
                'processor_name': transaction['processor_name'],
                'processor_transaction_id': transaction.get('processor_transaction_id'),
                'metadata': transaction.get('metadata', {}),
                'error_code': transaction.get('error_code'),
                'error_details': transaction.get('error_details')
            }
            
            # Add void information if voided
            if transaction['status'] == 'voided':
                details['void_reason'] = transaction.get('void_reason')
                details['voided_at'] = transaction.get('voided_at')
            
            # Add refund information for refund transactions
            if transaction['transaction_type'] == 'refund':
                details['original_transaction_id'] = transaction.get('original_transaction_id')
                details['refund_reason'] = transaction.get('refund_reason')
            
            status_data['details'] = details
        
        logger.info(f"Transaction status retrieved: {transaction_id} - {transaction['status']}")
        
        return create_response(200, True, status_data)
        
    except Exception as e:
        logger.error(f"Error getting transaction status: {str(e)}", exc_info=True)
        return create_response(500, False, error=f"Failed to get transaction status: {str(e)}")
