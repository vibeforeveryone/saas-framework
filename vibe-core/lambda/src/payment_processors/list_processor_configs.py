# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
List Payment Processor Configurations
Retrieves all processor configurations for a customer (without sensitive data)
Supports AWS API Gateway V2 with header-based authentication
"""
import json
import boto3
import traceback
from datetime import datetime
from decimal import Decimal
from boto3.dynamodb.conditions import Key
from utils.track_api_call import tracked
from utils.lambda_utils import extract_user_context,decimal_default,create_response

dynamodb = boto3.resource('dynamodb')
PROCESSOR_CONFIG_TABLE = dynamodb.Table('PaymentProcessorConfig')


@tracked
def lambda_handler(event, context):
    """
    List payment processor configurations
    GET /customers/{customer_id}/processors
    
    Query parameters:
    - include_inactive: Include inactive processors (default: true)
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
        
        if not customer_id:
            return create_response(400, False, error="Missing customer_id")
        
        # Get query parameters
        query_params = event.get('queryStringParameters', {}) or {}
        include_inactive = query_params.get('include_inactive', 'true').lower() == 'true'
        
        print(f"Listing processors for customer: {customer_id}")
        
        # Query configurations for the customer
        response = PROCESSOR_CONFIG_TABLE.query(
            KeyConditionExpression=Key('customer_id').eq(customer_id)
        )
        
        items = response.get('Items', [])
        print(f"Found {len(items)} total processors")
        
        # Filter by active status if requested
        if not include_inactive:
            items = [item for item in items if item.get('is_active', False)]
            print(f"Filtered to {len(items)} active processors")
        
        # Remove sensitive encrypted fields and add masked indicators
        sanitized_configs = []
        for item in items:
            config = item.copy()
            
            # Remove encrypted fields
            has_api_key = 'api_key_encrypted' in config
            has_api_secret = 'api_secret_encrypted' in config
            
            config.pop('api_key_encrypted', None)
            config.pop('api_secret_encrypted', None)
            
            # Add masked indicators
            if has_api_key:
                config['api_key'] = '***encrypted***'
            if has_api_secret:
                config['api_secret'] = '***encrypted***'
            
            sanitized_configs.append(config)
        
        # Sort by processor_name
        sanitized_configs.sort(key=lambda x: x.get('processor_name', ''))
        
        # Find active processor
        active_processor = next(
            (c for c in sanitized_configs if c.get('is_active')),
            None
        )
        
        result_data = {
            'customer_id': customer_id,
            'total_configs': len(sanitized_configs),
            'active_processor': active_processor.get('processor_name') if active_processor else None,
            'configurations': sanitized_configs
        }
        
        print(f"Returning {len(sanitized_configs)} processor configs for {customer_id}")
        
        return create_response(200, True, result_data)
        
    except Exception as e:
        print(f"Error listing processor configs: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to list processor configurations: {str(e)}")
