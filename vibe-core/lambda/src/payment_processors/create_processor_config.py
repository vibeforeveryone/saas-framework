# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Create Payment Processor Configuration
Stores encrypted processor configuration in DynamoDB
Supports AWS API Gateway V2 with header-based authentication
"""
import json
import boto3
import traceback
from datetime import datetime
from decimal import Decimal
from utils.track_api_call import tracked
from utils.lambda_utils import extract_user_context,decimal_default,create_response

dynamodb = boto3.resource('dynamodb')
PROCESSOR_CONFIG_TABLE = dynamodb.Table('PaymentProcessorConfig')



def encrypt_sensitive_data(data):
    """Placeholder for encryption - implement with AWS KMS or similar"""
    # In production, use AWS KMS or similar encryption service
    import base64
    return base64.b64encode(data.encode()).decode()

@tracked
def lambda_handler(event, context):
    """
    Create new payment processor configuration
    POST /customers/{customer_id}/processors
    
    Expected payload:
    {
        "processor_name": "MerchantOne Primary",
        "processor_type": "merchantone",
        "is_test_mode": true,
        "api_key": "sensitive_key",
        "api_secret": "sensitive_secret",
        "merchant_id": "merchant123",
        "endpoint_url": "https://api.example.com"
    }
    """
    print(f"Event: {json.dumps(event, default=decimal_default)}")
    print(f"Context: {context}")
    
    try:
        http_method = event.get('requestContext', {}).get('http', {}).get('method')
        
        if http_method == 'OPTIONS':
            return create_response(200, True)
        
        user_context = extract_user_context(event)
        print(f"User context: {json.dumps(user_context)}")
        
        path_params = event.get('pathParameters', {})
        customer_id = path_params.get('customer_id') or user_context['customer_id']
        
        if not customer_id:
            return create_response(400, False, error="Missing customer_id")
        
        # Parse body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        # Validate required fields
        required_fields = ['processor_name', 'processor_type']
        missing_fields = [field for field in required_fields if not body.get(field)]
        
        if missing_fields:
            return create_response(400, False, error=f"Missing required fields: {', '.join(missing_fields)}")
        
        processor_name = body['processor_name']
        processor_type = body['processor_type'].lower()
        
        # Validate processor type
        valid_processors = ['mock', 'merchantone', 'paysafe', 'paymentnerds']
        if processor_type not in valid_processors:
            return create_response(400, False, error=f"Invalid processor_type. Must be one of: {', '.join(valid_processors)}")
        
        # Encrypt sensitive fields
        encrypted_api_key = None
        encrypted_api_secret = None
        
        if body.get('api_key'):
            encrypted_api_key = encrypt_sensitive_data(body['api_key'])
            print("Encrypted API key")
        
        if body.get('api_secret'):
            encrypted_api_secret = encrypt_sensitive_data(body['api_secret'])
            print("Encrypted API secret")
        
        timestamp = datetime.utcnow().isoformat()
        
        config_record = {
            'customer_id': customer_id,
            'processor_name': processor_name,
            'processor_type': processor_type,
            'is_active': False,
            'is_test_mode': body.get('is_test_mode', True),
            'merchant_id': body.get('merchant_id', ''),
            'endpoint_url': body.get('endpoint_url', ''),
            'additional_config': body.get('additional_config', {}),
            'created_at': timestamp,
            'modified_at': timestamp,
            'created_by': user_context['user_id'] or 'system',
            'modified_by': user_context['user_id'] or 'system'
        }
        
        if encrypted_api_key:
            config_record['api_key_encrypted'] = encrypted_api_key
        
        if encrypted_api_secret:
            config_record['api_secret_encrypted'] = encrypted_api_secret
        
        PROCESSOR_CONFIG_TABLE.put_item(Item=config_record)
        
        # Remove encrypted values from response
        response_config = config_record.copy()
        response_config.pop('api_key_encrypted', None)
        response_config.pop('api_secret_encrypted', None)
        
        if encrypted_api_key:
            response_config['api_key'] = '***encrypted***'
        if encrypted_api_secret:
            response_config['api_secret'] = '***encrypted***'
        
        print(f"Created processor config: {customer_id}/{processor_name}")
        
        return create_response(201, True, {
            'config': response_config,
            'message': 'Processor configuration created successfully'
        })
        
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {str(e)}")
        print(traceback.format_exc())
        return create_response(400, False, error="Invalid JSON in request body")
    except Exception as e:
        print(f"Error creating processor config: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to create processor configuration: {str(e)}")
