"""
List Customers
Lists customers — super users see all, regular users see only their own record.
Supports AWS API Gateway V2 with JWT-based authentication.
Copyright (c) Vibe For Everyone, LLC
Author: Christopher Niven
"""
import json
import boto3
import logging
from datetime import datetime

from boto3.dynamodb.conditions import Key
from utils.lambda_utils import extract_user_context, decimal_default
from utils.track_api_call import tracked

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('Customers')


def get_cors_headers():
    return {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
        'Access-Control-Max-Age': '600'
    }


def create_response(status_code, success, data=None, error=None):
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

@tracked
def lambda_handler(event, context):
    """
    List customers.
    GET /customers

    Super users receive the full customer list (optionally filtered by company_name).
    Regular users receive only their own customer record.

    Query parameters (super user only):
        limit        - max records to return (default 100)
        company_name - filter by exact company name via CustomerIndex
    """

 
    try:
        # Handle preflight OPTIONS request
        if event.get('requestContext', {}).get('http', {}).get('method') == 'OPTIONS':
            return {'statusCode': 200, 'headers': get_cors_headers(), 'body': ''}


        logger.info ('LIST_CUSTOMERS.py LOG_START   ')
        logger.info(f"LIST_CUSTOMERS.py LOG_Event: {json.dumps(event, default=decimal_default)}")

       
       

        # Verify JWT and extract caller identity
        user_context = extract_user_context(event)
        logger.info(f"LIST_CUSTOMERS.py 1.0 LOG_User context: {json.dumps(user_context)}")
        
        if user_context.get('statusCode'):
            logger.warning(f"[LIST_CUSTOMERS.py 1.1] list_customers blocked — {user_context}")
            return user_context  # 401 — invalid or missing token

        logger.info(f"[LIST_CUSTOMERS.py 1.2] list_customers — verified context: {user_context}")   # REMOVE — exposes identity
        logger.info(f"[LIST_CUSTOMERS.py 1.3] Routing — is_super_user: {user_context['is_super_user']}")

        logger.info(f"LIST_CUSTOMERS.py 1.4 List customers request by user {user_context['user_key']} "
                    f"(customer: {user_context['customer_id']}, "
                    f"super_user: {user_context['is_super_user']})")

        logger.info(f"[LIST_CUSTOMERS.py 1.5]")
        # ----------------------------------------------------------------
        # Non-super users: return only their own customer record
        # ----------------------------------------------------------------
        if not user_context['is_super_user']:

            logger.info(f"[LIST_CUSTOMERS.py 1.6]")
            response = table.get_item(
                Key={'customer_id': user_context['customer_id']}
            )
            customer = response.get('Item')
            logger.info(f"[LIST_CUSTOMERS.py 1.6]")
            if not customer:
                logger.info(f"[LIST_CUSTOMERS.py 1.57]")
                logger.info ('LIST_CUSTOMERS.py LOG_END no  customers (404)  ')

                return create_response(404, False, error="Customer record not found")

            logger.info ('LIST_CUSTOMERS.py LOG_END single customer (200) ')

            logger.info(f"[LIST_CUSTOMERS.py 1.8]")
            return create_response(200, True, {
                'customers': [customer],
                'count': 1,
                'has_more': False
            })
        
        logger.info(f"[LIST_CUSTOMERS.py 1.9]")
        # ----------------------------------------------------------------
        # Super users: full list with optional filtering and pagination
        # ----------------------------------------------------------------
        query_params = event.get('queryStringParameters') or {}
        limit = int(query_params.get('limit', 100))
        company_name = query_params.get('company_name')

        logger.info(f"[LIST_CUSTOMERS.py 2.0]")
        if company_name:

            logger.info(f"[LIST_CUSTOMERS.py 2.1]")

            logger.info(f"Querying by company_name: {company_name}")

            logger.info(f"[LIST_CUSTOMERS.py 2.3]")
            response = table.query(
                IndexName='CustomerIndex',
                KeyConditionExpression=Key('company_name').eq(company_name),
                ScanIndexForward=True,
                Limit=limit
            )
        else:
            logger.info("Performing full table scan")
            response = table.scan(Limit=limit)

        logger.info(f"[LIST_CUSTOMERS.py 3.0]")

        customers = response.get('Items', [])
        customers = sorted(customers, key=lambda x: x.get('customer_id', ''))

        logger.info(f"[LIST_CUSTOMERS.py 3.2")

        logger.info(f"Retrieved {len(customers)} customers for super user {user_context['user_key']}")

        logger.info ('[LIST_CUSTOMERS.py] LOG_END multiple customers (200)  ')

        logger.info(f"[LIST_CUSTOMERS.py 3.3]")

        return create_response(200, True, {
            'customers': customers,
            'count': len(customers),
            'has_more': 'LastEvaluatedKey' in response
        })

    except Exception as ex2:

        logger.info(f"[LIST_CUSTOMERS.py 5.0]")
        
        logger.error(f"Error listing customers: {str(ex2)}")

        logger.info(f"[LIST_CUSTOMERS.py 5.2]")
   
        import traceback
        traceback.print_exc()
        
        logger.info(f"[LIST_CUSTOMERS.py 5.3]")
        
        
        return create_response(500, False, error=f"Failed to list customers: {str(ex2)}")