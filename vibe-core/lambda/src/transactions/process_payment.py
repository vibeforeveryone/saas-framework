# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Process Payment Transaction
Main endpoint for processing customer payments through active payment processor
Supports AWS API Gateway V2 with header-based authentication
"""
import json
import boto3
import traceback
from datetime import datetime
from decimal import Decimal
from utils.track_api_call import tracked
from utils.lambda_utils import extract_user_context,decimal_default,create_response


# AWS Clients
dynamodb = boto3.resource('dynamodb')

# Hardcoded table name
TRANSACTIONS_TABLE = dynamodb.Table('PaymentTransaction')


@tracked
def lambda_handler(event, context):
    """
    Process a payment transaction
    POST /customers/{customer_id}/transactions
    
    Expected payload:
    {
        "customer_id": "cust_123",
        "amount": 99.99,
        "currency": "USD",
        "payment_method": {
            "type": "card",
            "card_number": "4111111111111111",
            "exp_month": 12,
            "exp_year": 2025,
            "cvv": "123",
            "cardholder_name": "John Doe"
        },
        "customer_info": {
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "+1234567890",
            "address": {
                "street": "123 Main St",
                "city": "New York",
                "state": "NY",
                "zip": "10001",
                "country": "US"
            }
        },
        "metadata": {
            "order_id": "ORD-12345",
            "description": "Product purchase"
        }
    }
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
        
        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        # Validate required fields
        required_fields = ['customer_id', 'amount', 'currency', 'payment_method']
        missing_fields = [field for field in required_fields if not body.get(field)]
        
        if missing_fields:
            return create_response(
                400, False,
                error=f"Missing required fields: {', '.join(missing_fields)}"
            )
        
        customer_id = body['customer_id']
        amount = float(body['amount'])
        currency = body['currency']
        payment_method = body['payment_method']
        customer_info = body.get('customer_info', {})
        metadata = body.get('metadata', {})
        
        # Validate amount
        if amount <= 0:
            return create_response(400, False, error="Amount must be greater than 0")
        
        if amount > 999999.99:
            return create_response(400, False, error="Amount exceeds maximum limit of 999,999.99")
        
        # Validate currency
        supported_currencies = ['USD', 'EUR', 'GBP', 'CAD', 'AUD']
        if currency not in supported_currencies:
            return create_response(
                400, False,
                error=f"Unsupported currency. Supported: {', '.join(supported_currencies)}"
            )
        
        # Generate transaction ID
        transaction_id = f"txn_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{customer_id[:8]}"
        timestamp = datetime.utcnow().isoformat()
        
        # Add tracking metadata
        metadata['customer_id'] = customer_id
        metadata['customer_id'] = customer_id
        metadata['processed_by'] = user_context['user_id']
        metadata['ip_address'] = event.get('requestContext', {}).get('http', {}).get('sourceIp')
        
        # In production, this would call the actual payment processor
        # For now, simulate successful payment
        print(f"Processing payment: {amount} {currency} for customer {customer_id}")
        
        # Simulate processor response
        payment_success = True
        processor_transaction_id = f"proc_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        
        # Create transaction record
        transaction_record = {
            'transaction_id': transaction_id,
            'customer_id': customer_id,
            'customer_id': customer_id,
            'amount': Decimal(str(amount)),
            'currency': currency,
            'status': 'completed' if payment_success else 'failed',
            'transaction_type': 'payment',
            'processor_type': 'simulated',
            'processor_transaction_id': processor_transaction_id,
            'payment_method_type': payment_method.get('type', 'unknown'),
            'customer_email': customer_info.get('email'),
            'customer_name': customer_info.get('name'),
            'created_at': timestamp,
            'created_by': user_context['user_id'] or 'system',
            'metadata': metadata
        }
        
        # Store transaction record
        TRANSACTIONS_TABLE.put_item(Item=transaction_record)
        print(f"Transaction record created: {transaction_id}")
        
        # Prepare response
        response_data = {
            'transaction_id': transaction_id,
            'processor_transaction_id': processor_transaction_id,
            'status': 'completed' if payment_success else 'failed',
            'amount': amount,
            'currency': currency,
            'timestamp': timestamp,
            'message': 'Payment processed successfully'
        }
        
        if not payment_success:
            print(f"Payment failed: {transaction_id}")
            return create_response(402, False, data=response_data)
        
        print(f"Payment successful: {transaction_id}")
        return create_response(200, True, response_data)
        
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {str(e)}")
        print(traceback.format_exc())
        return create_response(400, False, error="Invalid JSON in request body")
    except Exception as e:
        print(f"Error processing payment: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Payment processing failed: {str(e)}")
