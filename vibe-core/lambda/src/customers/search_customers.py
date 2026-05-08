# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
import json
import boto3
import os
import logging
from boto3.dynamodb.conditions import Key, Attr

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
    Search customers with advanced filtering
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
        logger.info(f"Search customers request -  UserId: {user_id}")
        logger.info(f"Request event: {json.dumps(event)}")
        
        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        # Get search parameters
        company_name = body.get('company_name')
        email = body.get('email')
        name_search = body.get('name')
        status = body.get('status')
        limit = int(body.get('limit', 100))
        
        logger.info(f"Search criteria - company: {company_name}, email: {email}, name: {name_search}, status: {status}")
        
        # Build filter expressions
        filter_expressions = []
        
        if name_search:
            filter_expressions.append(Attr('name').contains(name_search))
        
        if status:
            filter_expressions.append(Attr('status').eq(status))
        
        # Perform query or scan based on available indexes
        if email:
            # Query using EmailIndex
            logger.info(f"Querying by email: {email}")
            response = table.query(
                IndexName='EmailIndex',
                KeyConditionExpression=Key('email').eq(email),
                Limit=limit
            )
        elif company_name:
            # Query using CustomerIndex
            logger.info(f"Querying by company_name: {company_name}")
            query_kwargs = {
                'IndexName': 'CustomerIndex',
                'KeyConditionExpression': Key('company_name').eq(company_name),
                'Limit': limit
            }
            
            # Add filter expressions if any
            if filter_expressions:
                filter_expression = filter_expressions[0]
                for expr in filter_expressions[1:]:
                    filter_expression = filter_expression & expr
                query_kwargs['FilterExpression'] = filter_expression
            
            response = table.query(**query_kwargs)
        else:
            # Full table scan with filters
            logger.info("Performing filtered table scan")
            scan_kwargs = {'Limit': limit}
            
            if filter_expressions:
                filter_expression = filter_expressions[0]
                for expr in filter_expressions[1:]:
                    filter_expression = filter_expression & expr
                scan_kwargs['FilterExpression'] = filter_expression
            
            response = table.scan(**scan_kwargs)
        
        customers = response.get('Items', [])
        
        # Sort by customer_id
        customers = sorted(customers, key=lambda x: x.get('customer_id', ''))
        
        result_data = {
            'customers': customers,
            'count': len(customers),
            'has_more': 'LastEvaluatedKey' in response,
            'search_criteria': {
                'company_name': company_name,
                'email': email,
                'name': name_search,
                'status': status
            }
        }
        
        logger.info(f"Found {len(customers)} customers matching search criteria by user {user_id} ")
        return create_response(200, True, result_data)
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return create_response(400, False, error="Invalid JSON in request body")
        
    except Exception as e:
        logger.error(f"Error searching customers: {str(e)}")
        import traceback
        traceback.print_exc()
        return create_response(500, False, error=f"Failed to search customers: {str(e)}")
