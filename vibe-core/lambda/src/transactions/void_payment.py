# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Void Payment Transaction
Cancel/void a payment before it settles
"""
import json
import boto3
import os
import logging
from datetime import datetime
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
    Void/cancel a payment transaction
    
    Expected payload:
    {
        "transaction_id": "txn_20250115120000_cust123",
        "reason": "Customer cancelled order"
    }
    """
    try:
        # Handle OPTIONS request
        if event.get('httpMethod') == 'OPTIONS':
            return create_response(200, True)
        
        logger.info(f"Void payment request: {json.dumps(event, default=str)}")
        
        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        # Validate required fields
        transaction_id = body.get('transaction_id')
        if not transaction_id:
            return create_response(
                400, False,
                error="transaction_id is required"
            )
        
        reason = body.get('reason', 'Transaction voided')
        
        # Get original transaction
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
        
        original_transaction = items[0]
        
        # Validate transaction can be voided
        if original_transaction['transaction_type'] != 'payment':
            return create_response(
                400, False,
                error=f"Cannot void transaction of type: {original_transaction['transaction_type']}"
            )
        
        # Check transaction status
        current_status = original_transaction['status']
        if current_status not in ['completed', 'pending', 'authorized']:
            return create_response(
                400, False,
                error=f"Cannot void transaction with status: {current_status}"
            )
        
        if current_status == 'voided':
            return create_response(
                400, False,
                error="Transaction has already been voided"
            )
        
        if current_status == 'settled':
            return create_response(
                400, False,
                error="Cannot void settled transaction. Use refund instead."
            )
        
        # Check if transaction has been refunded
        if original_transaction.get('refund_status') in ['partially_refunded', 'fully_refunded']:
            return create_response(
                400, False,
                error="Cannot void transaction that has been refunded"
            )
        
        # Get the processor configuration
        company_name = original_transaction['company_name']
        processor_config = get_active_processor_config(company_name)
        
        if not processor_config:
            return create_response(
                404, False,
                error=f"No active payment processor configured for company: {company_name}"
            )
        
        # Create processor instance
        processor = ProcessorFactory.create_from_config_record(processor_config)
        
        # Process void
        logger.info(f"Voiding transaction: {transaction_id}")
        processor_transaction_id = original_transaction.get('processor_transaction_id')
        
        void_response = processor.void_payment(
            transaction_id=processor_transaction_id,
            reason=reason
        )
        
        timestamp = datetime.utcnow().isoformat()
        
        # Update transaction status
        if void_response.success:
            transactions_table.update_item(
                Key={'transaction_id': transaction_id},
                UpdateExpression='SET #status = :voided, void_reason = :reason, voided_at = :timestamp, updated_at = :timestamp',
                ExpressionAttributeNames={
                    '#status': 'status'
                },
                ExpressionAttributeValues={
                    ':voided': 'voided',
                    ':reason': reason,
                    ':timestamp': timestamp
                }
            )
            
            logger.info(f"Transaction voided successfully: {transaction_id}")
        else:
            # Store void attempt even if failed
            transactions_table.update_item(
                Key={'transaction_id': transaction_id},
                UpdateExpression='SET void_attempted = :attempted, void_error = :error, updated_at = :timestamp',
                ExpressionAttributeValues={
                    ':attempted': True,
                    ':error': void_response.error_details,
                    ':timestamp': timestamp
                }
            )
        
        # Prepare response
        response_data = {
            'transaction_id': transaction_id,
            'processor_void_id': void_response.transaction_id,
            'status': void_response.status,
            'amount': float(original_transaction['amount']),
            'currency': original_transaction['currency'],
            'timestamp': timestamp,
            'success': void_response.success,
            'message': void_response.message,
            'reason': reason
        }
        
        if not void_response.success:
            response_data['error_code'] = void_response.error_code
            response_data['error_details'] = void_response.error_details
            
            logger.warning(f"Void failed: {void_response.error_details}")
            return create_response(402, False, data=response_data)
        
        return create_response(200, True, response_data)
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return create_response(400, False, error="Invalid JSON in request body")
    
    except Exception as e:
        logger.error(f"Error voiding transaction: {str(e)}", exc_info=True)
        return create_response(500, False, error=f"Void processing failed: {str(e)}")
