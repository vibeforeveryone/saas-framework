# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Batch Payment Processor
Process multiple payments in a single request
"""
import json
import boto3
import os
import logging
from datetime import datetime
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, as_completed
from cors_utils import create_response
from payment.processor_factory import ProcessorFactory
from payment_processors.get_processor_config import get_active_processor_config
from utils.track_api_call import tracked
from utils.lambda_utils import extract_user_context,decimal_default,create_response


logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
transactions_table = dynamodb.Table('TransactionsTable')

# Maximum batch size
MAX_BATCH_SIZE = 100


def process_single_payment(payment_data, company_name, processor):
    """
    Process a single payment in the batch
    
    Args:
        payment_data: Payment details
        company_name: Company identifier
        processor: Payment processor instance
    
    Returns:
        Result dict with transaction details
    """
    try:
        customer_id = payment_data['customer_id']
        amount = float(payment_data['amount'])
        currency = payment_data['currency']
        payment_method = payment_data['payment_method']
        customer_info = payment_data.get('customer_info', {})
        metadata = payment_data.get('metadata', {})
        
        # Process payment
        payment_response = processor.process_payment(
            amount=amount,
            currency=currency,
            payment_method=payment_method,
            customer_info=customer_info,
            metadata=metadata
        )
        
        # Create transaction record
        transaction_id = f"txn_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{customer_id[:8]}"
        timestamp = datetime.utcnow().isoformat()
        
        transaction_record = {
            'transaction_id': transaction_id,
            'company_name': company_name,
            'customer_id': customer_id,
            'amount': Decimal(str(amount)),
            'currency': currency,
            'status': 'completed' if payment_response.success else 'failed',
            'transaction_type': 'payment',
            'processor_type': processor.processor_type,
            'processor_name': processor.processor_name,
            'processor_transaction_id': payment_response.transaction_id,
            'payment_method_type': payment_method.get('type', 'unknown'),
            'customer_email': customer_info.get('email'),
            'customer_name': customer_info.get('name'),
            'created_at': timestamp,
            'updated_at': timestamp,
            'metadata': metadata,
            'error_code': payment_response.error_code,
            'error_details': payment_response.error_details,
            'batch_id': metadata.get('batch_id')
        }
        
        # Store transaction
        transactions_table.put_item(Item=transaction_record)
        
        return {
            'success': payment_response.success,
            'transaction_id': transaction_id,
            'processor_transaction_id': payment_response.transaction_id,
            'customer_id': customer_id,
            'amount': amount,
            'currency': currency,
            'status': payment_response.status,
            'message': payment_response.message,
            'error_code': payment_response.error_code,
            'error_details': payment_response.error_details
        }
        
    except Exception as e:
        logger.error(f"Error processing payment for {payment_data.get('customer_id')}: {str(e)}")
        return {
            'success': False,
            'customer_id': payment_data.get('customer_id'),
            'amount': payment_data.get('amount'),
            'error_code': 'PROCESSING_ERROR',
            'error_details': str(e)
        }

@tracked
def lambda_handler(event, context):
    """
    Process batch of payments
    
    Expected payload:
    {
        "company_name": "acme-corp",
        "batch_id": "batch_20250115_001",
        "payments": [
            {
                "customer_id": "cust_001",
                "amount": 99.99,
                "currency": "USD",
                "payment_method": {...},
                "customer_info": {...},
                "metadata": {}
            },
            ...
        ],
        "parallel_processing": true,
        "stop_on_error": false
    }
    """
    try:
        # Handle OPTIONS request
        if event.get('httpMethod') == 'OPTIONS':
            return create_response(200, True)
        
        logger.info(f"Batch payment request: {json.dumps(event, default=str)}")
        
        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        # Validate required fields
        company_name = body.get('company_name')
        payments = body.get('payments', [])
        
        if not company_name:
            return create_response(
                400, False,
                error="company_name is required"
            )
        
        if not payments or not isinstance(payments, list):
            return create_response(
                400, False,
                error="payments array is required"
            )
        
        if len(payments) > MAX_BATCH_SIZE:
            return create_response(
                400, False,
                error=f"Batch size exceeds maximum of {MAX_BATCH_SIZE}"
            )
        
        batch_id = body.get('batch_id', f"batch_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}")
        parallel_processing = body.get('parallel_processing', True)
        stop_on_error = body.get('stop_on_error', False)
        
        # Add batch_id to each payment's metadata
        for payment in payments:
            if 'metadata' not in payment:
                payment['metadata'] = {}
            payment['metadata']['batch_id'] = batch_id
        
        # Get active processor
        logger.info(f"Getting active processor for company: {company_name}")
        processor_config = get_active_processor_config(company_name)
        
        if not processor_config:
            return create_response(
                404, False,
                error=f"No active payment processor configured for company: {company_name}"
            )
        
        # Create processor instance
        processor = ProcessorFactory.create_from_config_record(processor_config)
        
        logger.info(f"Processing batch of {len(payments)} payments")
        
        results = []
        start_time = datetime.utcnow()
        
        if parallel_processing and len(payments) > 1:
            # Process payments in parallel
            with ThreadPoolExecutor(max_workers=min(10, len(payments))) as executor:
                futures = {
                    executor.submit(
                        process_single_payment,
                        payment,
                        company_name,
                        processor
                    ): payment
                    for payment in payments
                }
                
                for future in as_completed(futures):
                    result = future.result()
                    results.append(result)
                    
                    # Stop on first error if requested
                    if stop_on_error and not result['success']:
                        logger.warning(f"Stopping batch due to error: {result['error_details']}")
                        # Cancel remaining futures
                        for f in futures:
                            f.cancel()
                        break
        else:
            # Process payments sequentially
            for payment in payments:
                result = process_single_payment(payment, company_name, processor)
                results.append(result)
                
                # Stop on error if requested
                if stop_on_error and not result['success']:
                    logger.warning(f"Stopping batch due to error: {result['error_details']}")
                    break
        
        end_time = datetime.utcnow()
        processing_duration = (end_time - start_time).total_seconds()
        
        # Calculate summary
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        
        total_amount = sum(r.get('amount', 0) for r in successful)
        
        summary = {
            'batch_id': batch_id,
            'company_name': company_name,
            'total_payments': len(payments),
            'processed': len(results),
            'successful': len(successful),
            'failed': len(failed),
            'success_rate': round(len(successful) / len(results) * 100, 2) if results else 0,
            'total_amount_processed': round(total_amount, 2),
            'processing_duration_seconds': round(processing_duration, 2),
            'stopped_early': stop_on_error and len(failed) > 0,
            'processor_type': processor_config['processor_type'],
            'processor_name': processor_config['processor_name']
        }
        
        response_data = {
            'summary': summary,
            'results': results,
            'timestamp': end_time.isoformat()
        }
        
        logger.info(
            f"Batch complete: {len(successful)}/{len(results)} successful, "
            f"${total_amount:.2f} processed in {processing_duration:.2f}s"
        )
        
        return create_response(200, True, response_data)
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return create_response(400, False, error="Invalid JSON in request body")
    
    except Exception as e:
        logger.error(f"Error processing batch: {str(e)}", exc_info=True)
        return create_response(500, False, error=f"Batch processing failed: {str(e)}")
