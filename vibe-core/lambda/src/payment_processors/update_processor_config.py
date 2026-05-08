# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Update Payment Processor Configuration
Updates existing processor configuration with optional re-encryption
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
    Update payment processor configuration
    PUT /customers/{customer_id}/processors/{processor_name}
    
    Payload (all fields optional except customer_id and processor_name):
    {
        "is_test_mode": true,
        "api_key": "new_key",
        "api_secret": "new_secret",
        "merchant_id": "merchant123",
        "endpoint_url": "https://api.example.com",
        "additional_config": {}
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
        
        # Get path parameters
        path_params = event.get('pathParameters', {})
        customer_id = path_params.get('customer_id') or user_context['customer_id']
        processor_name = path_params.get('processor_name')
        
        if not customer_id or not processor_name:
            return create_response(400, False, error="Missing customer_id or processor_name")
        
        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        if not body:
            return create_response(400, False, error="Update data is required")
        
        print(f"Updating processor config: {customer_id}/{processor_name}")
        
        # Check if configuration exists
        existing = PROCESSOR_CONFIG_TABLE.get_item(
            Key={
                'customer_id': customer_id,
                'processor_name': processor_name
            }
        )
        
        if 'Item' not in existing:
            return create_response(404, False, error=f"Processor configuration '{processor_name}' not found for {customer_id}")
        
        # Build update expression
        update_expr_parts = []
        expr_attr_values = {}
        expr_attr_names = {}
        
        # Update timestamp and modified_by
        timestamp = datetime.utcnow().isoformat()
        update_expr_parts.append('#modified_at = :modified_at')
        update_expr_parts.append('#modified_by = :modified_by')
        expr_attr_names['#modified_at'] = 'modified_at'
        expr_attr_names['#modified_by'] = 'modified_by'
        expr_attr_values[':modified_at'] = timestamp
        expr_attr_values[':modified_by'] = user_context['user_id'] or 'system'
        
        # Handle sensitive fields with encryption
        if 'api_key' in body:
            encrypted_key = encrypt_sensitive_data(body['api_key'])
            update_expr_parts.append('api_key_encrypted = :api_key')
            expr_attr_values[':api_key'] = encrypted_key
            print("Updating encrypted api_key")
        
        if 'api_secret' in body:
            encrypted_secret = encrypt_sensitive_data(body['api_secret'])
            update_expr_parts.append('api_secret_encrypted = :api_secret')
            expr_attr_values[':api_secret'] = encrypted_secret
            print("Updating encrypted api_secret")
        
        # Handle non-sensitive fields
        updatable_fields = {
            'is_test_mode': 'is_test_mode',
            'merchant_id': 'merchant_id',
            'endpoint_url': 'endpoint_url',
            'additional_config': 'additional_config'
        }
        
        for field, db_field in updatable_fields.items():
            if field in body:
                update_expr_parts.append(f'#{db_field} = :{db_field}')
                expr_attr_names[f'#{db_field}'] = db_field
                expr_attr_values[f':{db_field}'] = body[field]
        
        if len(update_expr_parts) == 2:  # Only timestamp and modified_by
            return create_response(400, False, error="No valid fields to update")
        
        # Build complete update expression
        update_expression = 'SET ' + ', '.join(update_expr_parts)
        
        # Perform update
        response = PROCESSOR_CONFIG_TABLE.update_item(
            Key={
                'customer_id': customer_id,
                'processor_name': processor_name
            },
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expr_attr_names,
            ExpressionAttributeValues=expr_attr_values,
            ReturnValues='ALL_NEW'
        )
        
        updated_config = response['Attributes']
        
        # Remove encrypted fields from response
        updated_config.pop('api_key_encrypted', None)
        updated_config.pop('api_secret_encrypted', None)
        
        # Add masked indicators
        if 'api_key' in body:
            updated_config['api_key'] = '***encrypted***'
        if 'api_secret' in body:
            updated_config['api_secret'] = '***encrypted***'
        
        print(f"Updated processor config: {customer_id}/{processor_name}")
        
        return create_response(200, True, {
            'config': updated_config,
            'message': 'Processor configuration updated successfully'
        })
        
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {str(e)}")
        print(traceback.format_exc())
        return create_response(400, False, error="Invalid JSON in request body")
    except Exception as e:
        print(f"Error updating processor config: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to update processor configuration: {str(e)}")
