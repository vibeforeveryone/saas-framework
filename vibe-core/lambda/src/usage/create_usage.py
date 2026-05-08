# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Create Usage Tracking Record
Track user activity and application usage
Supports AWS API Gateway V2 with header-based authentication
"""
import json
import boto3
import traceback
from datetime import datetime, timezone
from decimal import Decimal

# AWS Clients
dynamodb = boto3.resource('dynamodb')

# Hardcoded table name
USAGE_TABLE = dynamodb.Table('UsageTable')

def decimal_default(obj):
    """JSON serializer for Decimal objects"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

def create_response(status_code, success, data=None, error=None):
    """Create standardized API response with enhanced CORS headers"""
    response = {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-User-Id,X-Provider-Id,X-Customer-Id',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
        },
        'body': json.dumps({
            'success': success,
            'data': data,
            'error': error,
            'timestamp': datetime.utcnow().isoformat()
        }, default=decimal_default)
    }
    return response

def extract_user_context(event):
    """Extract user context from authenticated headers"""
    headers = event.get('headers', {})
    
    user_id = headers.get('x-user-id') or headers.get('X-User-Id')
    provider_id = headers.get('x-provider-id') or headers.get('X-Provider-Id')
    customer_id = headers.get('x-customer-id') or headers.get('X-Customer-Id')
    
    return {
        'user_id': user_id,
        'provider_id': provider_id,
        'customer_id': customer_id
    }

def lambda_handler(event, context):
    """
    Create a new usage tracking record
    POST /usage
    
    Expected payload:
    {
        "customer_id": "acme-corp",
        "user_id": "user_123",
        "application_id": "app_crm",
        "app_page_id": "dashboard",
        "message": "User viewed dashboard",
        "application_line_number": "150",
        "user_data": {
            "action": "view",
            "duration_seconds": 45
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
        
        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        if not body:
            return create_response(400, False, error="Invalid or missing request body")
        
        # Validate required fields
        required_fields = ['customer_id', 'user_id', 'application_id', 'app_page_id', 'message']
        missing_fields = [field for field in required_fields if not body.get(field)]
        
        if missing_fields:
            return create_response(
                400, False,
                error=f"Missing required fields: {', '.join(missing_fields)}"
            )
        
        # Generate timestamp if not provided
        timestamp = body.get('timestamp')
        if not timestamp:
            timestamp = datetime.now(timezone.utc).isoformat()
        
        # Prepare usage record
        usage_record = {
            'company_name': str(body['customer_id']),
            'user_name': str(body['user_id']),
            'timestamp': timestamp,
            'app_name': str(body['application_id']),
            'app_page_id': str(body['app_page_id']),
            'application_line_number': str(body.get('application_line_number', '')),
            'message': str(body['message']),
            'user_data': body.get('user_data', {}),
            'created_by': user_context['user_id'] or body['user_id'],
            'customer_id': user_context['customer_id'] or body.get('customer_id', '')
        }
        
        # Validate user_data is a dictionary
        if not isinstance(usage_record['user_data'], dict):
            return create_response(
                400, False,
                error="user_data must be a dictionary of name/value pairs"
            )
        
        # Store in DynamoDB
        USAGE_TABLE.put_item(Item=usage_record)
        
        print(f"Created usage record: {usage_record['company_name']}/{usage_record['user_name']}/{timestamp}")
        
        return create_response(201, True, {
            'usage_record': usage_record,
            'message': 'Usage data created successfully'
        })
        
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {str(e)}")
        print(traceback.format_exc())
        return create_response(400, False, error="Invalid JSON in request body")
    except Exception as e:
        print(f"Error creating usage data: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to create usage data: {str(e)}")

def create_usage_data(customer_id, user_id, application_id, app_page_id, message, 
                     application_line_number=None, user_data=None, timestamp=None):
    """
    Utility function to create usage data programmatically
    This can be imported and called by other SaaS applications
    
    Args:
        customer_id: Company identifier
        user_id: User identifier
        application_id: Application identifier
        app_page_id: Page/section identifier
        message: Usage event message
        application_line_number: Optional line number reference
        user_data: Optional dictionary of additional data
        timestamp: Optional timestamp (ISO format)
    
    Returns:
        tuple: (success: bool, result: dict or error_message: str)
    """
    try:
        if not timestamp:
            timestamp = datetime.now(timezone.utc).isoformat()
        
        usage_record = {
            'company_name': str(customer_id),
            'user_name': str(user_id),
            'timestamp': timestamp,
            'app_name': str(application_id),
            'app_page_id': str(app_page_id),
            'application_line_number': str(application_line_number or ''),
            'message': str(message),
            'user_data': user_data or {},
            'created_by': str(user_id)
        }
        
        USAGE_TABLE.put_item(Item=usage_record)
        print(f"Programmatically created usage record: {customer_id}/{user_id}")
        
        return True, usage_record
        
    except Exception as e:
        print(f"Error in create_usage_data: {str(e)}")
        print(traceback.format_exc())
        return False, str(e)
