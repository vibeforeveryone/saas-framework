# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Create Dispute
Create a dispute record for a transaction
"""
import json
import boto3
import os
from utils.http_api_compat import normalize_event, get_http_method, get_path_parameter, get_query_parameter, parse_json_body
import logging
from datetime import datetime
from decimal import Decimal
from boto3.dynamodb.conditions import Key
from utils.cors_utils import create_response
from utils.track_api_call import tracked

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
disputes_table = dynamodb.Table('Dispute')
transactions_table = dynamodb.Table('Transactions')

@tracked
def lambda_handler(event, context):
    """
    Create a dispute record
    
    Expected payload:
    {
        "transaction_id": "txn_20250115120000_cust123",
        "dispute_type": "chargeback|inquiry|fraud",
        "reason_code": "FRAUD|PRODUCT_NOT_RECEIVED|DUPLICATE|etc",
        "amount": 99.99,  // Optional: disputed amount
        "customer_dispute_reason": "Customer claims fraud",
        "evidence_required": true,
        "dispute_metadata": {
            "case_id": "CASE123",
            "network": "Visa",
            "arn": "74537604221111111111111"
        }
    }
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
    
    logger.info(f"Create dispute request - ProviderId: {provider_id}, UserId: {user_id}")
    logger.info(f"Request event: {json.dumps(event, default=str)}")
    # ... after creating dispute ...
    logger.info(f"Dispute created: {dispute_id} ({dispute_type}) for transaction {transaction_id} by user {user_id} (provider: {provider_id})")
    logger.warning(f"Transaction not found: {transaction_id} (user {user_id})")  # when not found

    try:
        # Handle OPTIONS request
        if get_http_method(event) == 'OPTIONS':
            return create_response(200, True)
        
        logger.info(f"Create dispute request: {json.dumps(event, default=str)}")
        
        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        # Validate required fields
        transaction_id = body.get('transaction_id')
        dispute_type = body.get('dispute_type')
        reason_code = body.get('reason_code')
        
        if not transaction_id:
            return create_response(
                400, False,
                error="transaction_id is required"
            )
        
        if not dispute_type or dispute_type not in ['chargeback', 'inquiry', 'fraud']:
            return create_response(
                400, False,
                error="dispute_type must be one of: chargeback, inquiry, fraud"
            )
        
        # Get original transaction
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
        
        # Validate transaction is eligible for dispute
        if transaction['status'] not in ['completed', 'settled']:
            return create_response(
                400, False,
                error=f"Cannot dispute transaction with status: {transaction['status']}"
            )
        
        # Generate dispute ID
        dispute_id = f"disp_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{transaction_id[-8:]}"
        timestamp = datetime.utcnow().isoformat()
        
        # Get disputed amount (default to full transaction amount)
        disputed_amount = body.get('amount')
        if disputed_amount is None:
            disputed_amount = float(transaction['amount'])
        else:
            disputed_amount = float(disputed_amount)
            
            # Validate disputed amount doesn't exceed transaction amount
            if disputed_amount > float(transaction['amount']):
                return create_response(
                    400, False,
                    error="Disputed amount cannot exceed transaction amount"
                )
        
        # Create dispute record
        dispute_record = {
            'dispute_id': dispute_id,
            'created_by': user_id,  # ADD THIS - tracks who created dispute
            'transaction_id': transaction_id,
            'company_name': transaction['company_name'],
            'customer_id': transaction['customer_id'],
            'customer_email': transaction.get('customer_email'),
            'customer_name': transaction.get('customer_name'),
            'transaction_amount': Decimal(str(transaction['amount'])),
            'disputed_amount': Decimal(str(disputed_amount)),
            'currency': transaction['currency'],
            'dispute_type': dispute_type,
            'reason_code': reason_code,
            'customer_dispute_reason': body.get('customer_dispute_reason', ''),
            'status': 'open',
            'evidence_required': body.get('evidence_required', True),
            'processor_type': transaction['processor_type'],
            'processor_transaction_id': transaction.get('processor_transaction_id'),
            'created_at': timestamp,
            'updated_at': timestamp,
            'due_date': body.get('due_date'),  # Deadline to respond
            'metadata': body.get('dispute_metadata', {}),
            'evidence_submitted': False,
            'resolution': None,
            'resolution_date': None
        }
        
        # Store dispute
        disputes_table.put_item(Item=dispute_record)
        
        # Update transaction with dispute flag
        transactions_table.update_item(
            Key={'transaction_id': transaction_id},
            UpdateExpression='SET has_dispute = :has_dispute, dispute_id = :dispute_id, updated_at = :timestamp',
            ExpressionAttributeValues={
                ':has_dispute': True,
                ':dispute_id': dispute_id,
                ':timestamp': timestamp
            }
        )
        
        logger.info(f"Dispute created: {dispute_id} for transaction {transaction_id}")
        
        # Prepare response
        response_data = {
            'dispute_id': dispute_id,
            'transaction_id': transaction_id,
            'dispute_type': dispute_type,
            'reason_code': reason_code,
            'disputed_amount': disputed_amount,
            'currency': transaction['currency'],
            'status': 'open',
            'evidence_required': dispute_record['evidence_required'],
            'created_at': timestamp,
            'message': 'Dispute created successfully'
        }
        
        if dispute_record.get('due_date'):
            response_data['due_date'] = dispute_record['due_date']
        
        return create_response(201, True, response_data)
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return create_response(400, False, error="Invalid JSON in request body")
    
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return create_response(500, False, error=f"Failed: {str(e)}")