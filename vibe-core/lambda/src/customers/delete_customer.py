# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
import json
import boto3
import os
import logging

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
    Delete a customer
    """
    try:
        # Handle preflight OPTIONS request
        if event.get('httpMethod') == 'OPTIONS' or event.get('requestContext', {}).get('http', {}).get('method') == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': get_cors_headers(),
                'body': ''
            }

        # Extract user_id from headers (V2 best practice)
        headers = event.get('headers', {})
        user_id = (headers.get('X-User-Id') or headers.get('x-user-id') or 
                  headers.get('userId') or 'demo-user')
        
       
        # Log request context for debugging
        logger.info(f"Delete customer request -  UserId: {user_id}")
        logger.info(f"Request event: {json.dumps(event)}")
        
        # Get customer_id from path parameters
        path_params = event.get('pathParameters', {})
        customer_id = path_params.get('customer_id')
        
        if not customer_id:
            return create_response(400, False, error="customer_id is required")
        
        # Delete customer from DynamoDB
        response = table.delete_item(
            Key={'customer_id': customer_id},
            ReturnValues='ALL_OLD'
        )
        
        if 'Attributes' not in response:
            logger.warning(f"Customer not found: {customer_id} (requested by user {user_id})")
            return create_response(404, False, error=f"Customer {customer_id} not found")
        
        deleted_customer = response['Attributes']
        company_name = deleted_customer.get('company_name', 'Unknown')
        
        logger.info(f"Deleted customer: {customer_id} ({company_name}) by user {user_id} ")
        
        return create_response(200, True, {
            'deleted_customer': deleted_customer,
            'message': 'Customer deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Error deleting customer: {str(e)}")
        import traceback
        traceback.print_exc()
        return create_response(500, False, error=f"Failed to delete customer: {str(e)}")
