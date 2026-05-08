# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Activate Payment Processor
Sets a processor as active and deactivates all others for the customer
Ensures only ONE processor is active at a time per customer
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
    Activate a payment processor (deactivates all others for the customer)
    POST /customers/{customer_id}/processors/{processor_name}/activate
    
    Payload (optional):
    {
        "force": true  // Force activation even if processor has validation warnings
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
        body = {}
        if event.get('body'):
            if isinstance(event['body'], str):
                body = json.loads(event['body'])
            else:
                body = event['body']
        
        force = body.get('force', False)
        
        print(f"Activating processor: {customer_id}/{processor_name}, force: {force}")
        
        # Check if the processor to activate exists
        target_response = PROCESSOR_CONFIG_TABLE.get_item(
            Key={
                'customer_id': customer_id,
                'processor_name': processor_name
            }
        )
        
        if 'Item' not in target_response:
            return create_response(404, False, error=f"Processor configuration '{processor_name}' not found for {customer_id}")
        
        target_config = target_response['Item']
        
        # Validate processor configuration (basic checks)
        validation_warnings = []
        
        if target_config.get('processor_type') != 'mock':
            # Check for required credentials (except for mock processor)
            if not target_config.get('api_key_encrypted'):
                validation_warnings.append("Missing API key")
            
            processor_type = target_config.get('processor_type')
            if processor_type in ['merchantone', 'paymentnerds'] and not target_config.get('merchant_id'):
                validation_warnings.append("Missing merchant ID")
            
            if processor_type == 'paysafe' and not target_config.get('api_secret_encrypted'):
                validation_warnings.append("Missing API secret")
        
        # If there are warnings and not forcing, return validation error
        if validation_warnings and not force:
            print(f"Validation warnings: {validation_warnings}")
            return create_response(400, False, 
                error="Processor configuration has validation warnings",
                data={
                    'warnings': validation_warnings,
                    'message': 'Use force=true to activate anyway'
                }
            )
        
        # Get all processors for this customer
        all_processors = PROCESSOR_CONFIG_TABLE.query(
            KeyConditionExpression=Key('customer_id').eq(customer_id)
        )
        
        processors = all_processors.get('Items', [])
        
        # Find currently active processor
        currently_active = None
        for proc in processors:
            if proc.get('is_active') and proc['processor_name'] != processor_name:
                currently_active = proc['processor_name']
                break
        
        timestamp = datetime.utcnow().isoformat()
        
        # Deactivate all other processors
        deactivated_count = 0
        for proc in processors:
            if proc['processor_name'] != processor_name and proc.get('is_active'):
                PROCESSOR_CONFIG_TABLE.update_item(
                    Key={
                        'customer_id': customer_id,
                        'processor_name': proc['processor_name']
                    },
                    UpdateExpression='SET is_active = :inactive, modified_at = :timestamp, modified_by = :modified_by',
                    ExpressionAttributeValues={
                        ':inactive': False,
                        ':timestamp': timestamp,
                        ':modified_by': user_context['user_id'] or 'system'
                    }
                )
                deactivated_count += 1
                print(f"Deactivated processor: {proc['processor_name']}")
        
        # Activate the target processor
        updated_response = PROCESSOR_CONFIG_TABLE.update_item(
            Key={
                'customer_id': customer_id,
                'processor_name': processor_name
            },
            UpdateExpression='SET is_active = :active, modified_at = :timestamp, activated_at = :timestamp, modified_by = :modified_by',
            ExpressionAttributeValues={
                ':active': True,
                ':timestamp': timestamp,
                ':modified_by': user_context['user_id'] or 'system'
            },
            ReturnValues='ALL_NEW'
        )
        
        activated_config = updated_response['Attributes']
        
        # Remove encrypted fields from response
        activated_config.pop('api_key_encrypted', None)
        activated_config.pop('api_secret_encrypted', None)
        
        # Add masked indicators
        if 'api_key_encrypted' in target_config:
            activated_config['api_key'] = '***encrypted***'
        if 'api_secret_encrypted' in target_config:
            activated_config['api_secret'] = '***encrypted***'
        
        print(f"Activated processor: {customer_id}/{processor_name}")
        
        result_message = f"Processor '{processor_name}' activated successfully"
        if currently_active:
            result_message += f". Deactivated previous processor: '{currently_active}'"
        
        if validation_warnings:
            result_message += f". Warnings: {', '.join(validation_warnings)}"
        
        return create_response(200, True, {
            'config': activated_config,
            'message': result_message,
            'previously_active': currently_active,
            'deactivated_count': deactivated_count,
            'warnings': validation_warnings if validation_warnings else None,
            'activated_by': user_context['user_id']
        })
        
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {str(e)}")
        print(traceback.format_exc())
        return create_response(400, False, error="Invalid JSON in request body")
    except Exception as e:
        print(f"Error activating processor: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to activate processor: {str(e)}")
