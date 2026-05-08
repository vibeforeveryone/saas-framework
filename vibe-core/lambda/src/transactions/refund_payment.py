# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Refund Payment Transaction
Process refunds for completed payments
"""
import json
import boto3
import os
import logging
from datetime import datetime
from decimal import Decimal
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
    Refund a payment transaction
    
    Expected payload:
    {
        "transaction_id": "txn_20250115120000_cust123",
        "amount": 50.00,  // Optional: partial refund amount
        "reason": "Customer requested refund",
        "refund_metadata": {
            "refund_type": "full",
            "requested_by": "support@example.com"
        }
    }
    """
    try:
        # Handle OPTIONS request
        if event.get('httpMethod') == 'OPTIONS':
            return create_response(200, True)
        
        logger.info(f"Refund payment request: {json.dumps(event, default=str)}")
        
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
        
        refund_amount = body.get('amount')
        reason = body.get('reason', 'Refund requested')
        refund_metadata = body.get('refund_metadata', {})
        
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
        
        # Validate transaction can be refunded
        if original_transaction['transaction_type'] != 'payment':
            return create_response(
                400, False,
                error=f"Cannot refund transaction of type: {original_transaction['transaction_type']}"
            )
        
        if original_transaction['status'] not in ['completed', 'settled']:
            return create_response(
                400, False,
                error=f"Cannot refund transaction with status: {original_transaction['status']}"
            )
        
        # Check if already fully refunded
        if original_transaction.get('refund_status') == 'fully_refunded':
            return create_response(
                400, False,
                error="Transaction has already been fully refunded"
            )
        
        # Validate refund amount
        original_amount = float(original_transaction['amount'])
        refunded_amount = float(original_transaction.get('refunded_amount', 0))
        available_for_refund = original_amount - refunded_amount
        
        if refund_amount is None:
            # Full refund
            refund_amount = available_for_refund
        else:
            refund_amount = float(refund_amount)
            
            if refund_amount <= 0:
                return create_response(
                    400, False,
                    error="Refund amount must be greater than 0"
                )
            
            if refund_amount > available_for_refund:
                return create_response(
                    400, False,
                    error=f"Refund amount {refund_amount} exceeds available amount {available_for_refund}"
                )
        
        # Get the processor configuration used for original transaction
        company_name = original_transaction['company_name']
        processor_config = get_active_processor_config(company_name)
        
        if not processor_config:
            return create_response(
                404, False,
                error=f"No active payment processor configured for company: {company_name}"
            )
        
        # Create processor instance
        processor = ProcessorFactory.create_from_config_record(processor_config)
        
        # Process refund
        logger.info(f"Processing refund: {refund_amount} for transaction {transaction_id}")
        processor_transaction_id = original_transaction.get('processor_transaction_id')
        
        refund_response = processor.refund_payment(
            transaction_id=processor_transaction_id,
            amount=refund_amount,
            reason=reason
        )
        
        # Create refund transaction record
        refund_id = f"ref_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{transaction_id[-8:]}"
        timestamp = datetime.utcnow().isoformat()
        
        refund_record = {
            'transaction_id': refund_id,
            'company_name': company_name,
            'customer_id': original_transaction['customer_id'],
            'amount': Decimal(str(refund_amount)),
            'currency': original_transaction['currency'],
            'status': 'completed' if refund_response.success else 'failed',
            'transaction_type': 'refund',
            'original_transaction_id': transaction_id,
            'processor_type': processor_config['processor_type'],
            'processor_name': processor_config['processor_name'],
            'processor_transaction_id': refund_response.transaction_id,
            'refund_reason': reason,
            'customer_email': original_transaction.get('customer_email'),
            'customer_name': original_transaction.get('customer_name'),
            'created_at': timestamp,
            'updated_at': timestamp,
            'metadata': refund_metadata,
            'error_code': refund_response.error_code,
            'error_details': refund_response.error_details,
            'raw_response': refund_response.raw_response
        }
        
        # Store refund record
        transactions_table.put_item(Item=refund_record)
        
        # Update original transaction with refund info
        if refund_response.success:
            new_refunded_amount = refunded_amount + refund_amount
            refund_status = 'fully_refunded' if new_refunded_amount >= original_amount else 'partially_refunded'
            
            transactions_table.update_item(
                Key={'transaction_id': transaction_id},
                UpdateExpression='SET refunded_amount = :refunded, refund_status = :status, updated_at = :timestamp',
                ExpressionAttributeValues={
                    ':refunded': Decimal(str(new_refunded_amount)),
                    ':status': refund_status,
                    ':timestamp': timestamp
                }
            )
            
            logger.info(f"Refund successful: {refund_id}")
        
        # Prepare response
        response_data = {
            'refund_id': refund_id,
            'original_transaction_id': transaction_id,
            'processor_refund_id': refund_response.transaction_id,
            'status': refund_response.status,
            'refund_amount': refund_amount,
            'currency': original_transaction['currency'],
            'timestamp': timestamp,
            'success': refund_response.success,
            'message': refund_response.message
        }
        
        if not refund_response.success:
            response_data['error_code'] = refund_response.error_code
            response_data['error_details'] = refund_response.error_details
            
            logger.warning(f"Refund failed: {refund_response.error_details}")
            return create_response(402, False, data=response_data)
        
        return create_response(200, True, response_data)
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return create_response(400, False, error="Invalid JSON in request body")
    
    except Exception as e:
        logger.error(f"Error processing refund: {str(e)}", exc_info=True)
        return create_response(500, False, error=f"Refund processing failed: {str(e)}")
