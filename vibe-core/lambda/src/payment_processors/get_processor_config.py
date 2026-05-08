# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Get Payment Processor Configuration
Retrieves a specific processor configuration with decrypted sensitive data
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




def decrypt_sensitive_data(encrypted_data):
    """Placeholder for decryption - implement with AWS KMS or similar"""
    # In production, use AWS KMS or similar encryption service
    import base64
    try:
        return base64.b64decode(encrypted_data).decode()
    except:
        return None

@tracked
def lambda_handler(event, context):
    """
    Get payment processor configuration with decrypted credentials
    GET /customers/{customer_id}/processors/{processor_name}
    
    Query parameters:
    - decrypt: Set to 'true' to decrypt sensitive fields (requires authorization)
    """
    print(f"Event: {json.dumps(event, default=decimal_default)}")
    print(f"Context: {context}")
    
    try:
        http_method = event.get('requestContext', {}).get('http', {}).get('method')
        
        if http_method == 'OPTIONS':
            return create_response(200, True)
        
        user_context = extract_user_context(event)
        print(f"User context: {json.dumps(user_context)}")
        
        # Get path parameters
        path_params = event.get('pathParameters', {})
        customer_id = path_params.get('customer_id') or user_context['customer_id']
        processor_name = path_params.get('processor_name')
        
        if not customer_id or not processor_name:
            return create_response(400, False, error="Missing customer_id or processor_name")
        
        # Get query parameters
        query_params = event.get('queryStringParameters', {}) or {}
        should_decrypt = query_params.get('decrypt', 'false').lower() == 'true'
        
        print(f"Getting processor config: {customer_id}/{processor_name}, decrypt: {should_decrypt}")
        
        # Query configuration
        response = PROCESSOR_CONFIG_TABLE.get_item(
            Key={
                'customer_id': customer_id,
                'processor_name': processor_name
            }
        )
        
        if 'Item' not in response:
            return create_response(404, False, error=f"Processor configuration '{processor_name}' not found for {customer_id}")
        
        config = response['Item'].copy()
        
        # Handle decryption if requested
        if should_decrypt:
            print(f"Decrypting sensitive data for {processor_name} (requested by {user_context['user_id']})")
            
            # Decrypt sensitive fields
            if 'api_key_encrypted' in config:
                try:
                    config['api_key'] = decrypt_sensitive_data(config['api_key_encrypted'])
                    config.pop('api_key_encrypted')
                except Exception as e:
                    print(f"Failed to decrypt api_key: {str(e)}")
                    config['api_key'] = '***decryption_failed***'
                    config.pop('api_key_encrypted', None)
            
            if 'api_secret_encrypted' in config:
                try:
                    config['api_secret'] = decrypt_sensitive_data(config['api_secret_encrypted'])
                    config.pop('api_secret_encrypted')
                except Exception as e:
                    print(f"Failed to decrypt api_secret: {str(e)}")
                    config['api_secret'] = '***decryption_failed***'
                    config.pop('api_secret_encrypted', None)
        else:
            # Remove encrypted fields and add masked indicators
            has_api_key = 'api_key_encrypted' in config
            has_api_secret = 'api_secret_encrypted' in config
            
            config.pop('api_key_encrypted', None)
            config.pop('api_secret_encrypted', None)
            
            if has_api_key:
                config['api_key'] = '***encrypted***'
            if has_api_secret:
                config['api_secret'] = '***encrypted***'
        
        print(f"Retrieved processor config: {customer_id}/{processor_name}")
        
        return create_response(200, True, {'config': config})
        
    except Exception as e:
        print(f"Error getting processor config: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to get processor configuration: {str(e)}")
