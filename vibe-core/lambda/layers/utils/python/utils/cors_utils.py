# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
import json
import os
from functools import wraps

def get_cors_headers():
    """Generate CORS headers for API responses"""
    return {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
        'Access-Control-Max-Age': '600'
    }

def lambda_cors_handler(func):
    """Decorator to handle CORS for Lambda functions"""
    @wraps(func)
    def wrapper(event, context):
        # Handle preflight OPTIONS request
        if event.get('httpMethod') == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': get_cors_headers(),
                'body': ''
            }
        
        try:
            response = func(event, context)
            
            # Ensure response has CORS headers
            if 'headers' not in response:
                response['headers'] = {}
            
            response['headers'].update(get_cors_headers())
            
            return response
            
        except Exception as e:
            return {
                'statusCode': 500,
                'headers': get_cors_headers(),
                'body': json.dumps({
                    'success': False,
                    'error': str(e)
                })
            }
    
    return wrapper

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
        'body': json.dumps(body, default=str)
    }