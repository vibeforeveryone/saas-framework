# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
import json
import boto3
import os
import logging
from datetime import datetime, timezone

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('Customers')

def get_cors_headers():
    """Generate CORS headers for API responses"""
    return {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-User-Id',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
        'Access-Control-Max-Age': '600'
    }

def create_response(status_code, success, data=None, error=None):
    """Create standardized response with CORS headers"""
    body = {'success': success}
    
    if data is not None:
        body['data'] = data
    if error is not None:
        body['error'] = error
    
    return {
        'statusCode': status_code,
        'headers': get_cors_headers(),
        'body': json.dumps(body)
    }

def lambda_handler(event, context):
    """
    Update an existing customer
    """
    try:
        # Handle preflight OPTIONS request
        if event.get('httpMethod') == 'OPTIONS' or event.get('requestContext', {}).get('http', {}).get('method') == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': get_cors_headers(),
                'body': ''
            }

        # Extract  user_id from headers (V2 best practice)
        headers = event.get('headers', {})
        user_id = (headers.get('X-User-Id') or headers.get('x-user-id') or 
                  headers.get('userId') or 'demo-user')
        
        
        # Log request context for debugging
        logger.info(f"Update customer request -  UserId: {user_id}")
        logger.info(f"Request event: {json.dumps(event)}")
        
        # Get customer_id from path parameters
        path_params = event.get('pathParameters', {})
        customer_id = path_params.get('customer_id')
        
        if not customer_id:
            return create_response(400, False, error="customer_id is required")
        
        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        # Check if customer exists
        existing = table.get_item(Key={'customer_id': customer_id})
        if 'Item' not in existing:
            logger.warning(f"Customer not found: {customer_id} (requested by user {user_id})")
            return create_response(404, False, error=f"Customer {customer_id} not found")
        
        # Build update expression with updated_by from header
        update_expression = "SET updated_at = :updated_at, updated_by = :updated_by"
        expression_values = {
            ':updated_at': datetime.now(timezone.utc).isoformat(),
            ':updated_by': user_id  # Track who updated this
        }
        expression_names = {}
        
        # Add fields to update (including new address fields)
        updatable_fields = [
            'company_name', 'name', 'email', 'phone', 
            'address', 'city', 'state', 'zip', 'country', 'status'
        ]
        
        for field in updatable_fields:
            if field in body:
                # Handle reserved keywords
                if field == 'name':
                    expression_names['#name'] = 'name'
                    update_expression += f", #name = :{field}"
                elif field == 'status':
                    expression_names['#status'] = 'status'
                    update_expression += f", #status = :{field}"
                else:
                    update_expression += f", {field} = :{field}"
                expression_values[f':{field}'] = str(body[field])
        
        # Perform update
        update_kwargs = {
            'Key': {'customer_id': customer_id},
            'UpdateExpression': update_expression,
            'ExpressionAttributeValues': expression_values,
            'ReturnValues': 'ALL_NEW'
        }
        
        if expression_names:
            update_kwargs['ExpressionAttributeNames'] = expression_names
        
        response = table.update_item(**update_kwargs)
        
        updated_customer = response['Attributes']
        
        logger.info(f"Updated customer: {customer_id} ({updated_customer.get('company_name')}) by user {user_id} ")
        
        return create_response(200, True, {
            'customer': updated_customer,
            'message': 'Customer updated successfully'
        })
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return create_response(400, False, error="Invalid JSON in request body")
        
    except Exception as e:
        logger.error(f"Error updating customer: {str(e)}")
        import traceback
        traceback.print_exc()
        return create_response(500, False, error=f"Failed to update customer: {str(e)}")
