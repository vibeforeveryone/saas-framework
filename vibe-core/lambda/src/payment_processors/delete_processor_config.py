# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Delete Payment Processor Configuration
Removes a processor configuration from DynamoDB
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


@tracked
def lambda_handler(event, context):
    """
    Delete payment processor configuration
    DELETE /customers/{customer_id}/processors/{processor_name}
    
    Query parameters:
    - force: Set to 'true' to delete even if processor is active
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
        force = query_params.get('force', 'false').lower() == 'true'
        
        print(f"Deleting processor config: {customer_id}/{processor_name}, force: {force}")
        
        # Check if configuration exists
        existing = PROCESSOR_CONFIG_TABLE.get_item(
            Key={
                'customer_id': customer_id,
                'processor_name': processor_name
            }
        )
        
        if 'Item' not in existing:
            return create_response(404, False, error=f"Processor configuration '{processor_name}' not found for {customer_id}")
        
        config = existing['Item']
        
        # Check if processor is currently active
        is_active = config.get('is_active', False)
        
        if is_active and not force:
            print(f"Cannot delete active processor without force flag")
            return create_response(409, False, 
                error="Cannot delete active processor. Use force=true to delete anyway or deactivate first.",
                data={
                    'is_active': True,
                    'processor_name': processor_name,
                    'message': 'Deactivate the processor or use force=true'
                }
            )
        
        # Store config info before deletion for response
        deleted_info = {
            'processor_name': processor_name,
            'processor_type': config.get('processor_type'),
            'was_active': is_active,
            'created_at': config.get('created_at'),
            'is_test_mode': config.get('is_test_mode')
        }
        
        # Delete the configuration
        PROCESSOR_CONFIG_TABLE.delete_item(
            Key={
                'customer_id': customer_id,
                'processor_name': processor_name
            }
        )
        
        print(f"Deleted processor config: {customer_id}/{processor_name}")
        
        # If deleted processor was active, log warning
        if is_active:
            print(f"WARNING: Deleted ACTIVE processor: {customer_id}/{processor_name}")
        
        message = f"Processor configuration '{processor_name}' deleted successfully"
        if is_active:
            message += " (was active - no active processor now)"
        
        return create_response(200, True, {
            'message': message,
            'deleted_config': deleted_info,
            'deleted_by': user_context['user_id']
        })
        
    except Exception as e:
        print(f"Error deleting processor config: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to delete processor configuration: {str(e)}")
