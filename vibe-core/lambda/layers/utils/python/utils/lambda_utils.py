# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
lambda_utils.py — VFE SaaS Framework shared Lambda utilities
Place this file in: layers/utils/python/lambda_utils.py
"""
import json
import logging
from datetime import datetime
from decimal import Decimal
import os

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError


def create_response(status_code, success, data=None, error=None):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-User-Id,X-Customer-Id',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
        },
        'body': json.dumps({
            'success': success,
            'data': data,
            'error': error,
            'timestamp': datetime.utcnow().isoformat()
        }, default=decimal_default)
    }

#replaced with verion with JWT logic
#4/27
# def extract_user_context(event):
#     """Extract authenticated user context from API Gateway V2 headers."""
#     headers = event.get('headers', {})
#     return {
#         'user_id':    headers.get('x-user-id')    or headers.get('X-User-Id'),
#         'customer_id': headers.get('x-customer-id') or headers.get('X-Customer-Id')
#     }

import os
import logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

try:
    #from jwt.api_jwt import PyJWT, decode, decode_complete, encode
    import jwt
    logger.info(f"[JWT] imported ONE TIME")
except ImportError:
    jwt = None
    logger.info(f"[JWT] NOT imported ONE TIME")
    
JWT_SECRET = os.environ.get('JWT_SECRET', 'CHANGE-ME-BEFORE-PROD')

import boto3
import json

_secrets_client = boto3.client('secretsmanager')
_jwt_secret_cache = None

def _get_jwt_secret():
    global _jwt_secret_cache
    if _jwt_secret_cache is None:
        secret_name = os.environ.get('JWT_SECRET_NAME', 'vfeVer1/jwt-access-secret')
        logger.info(f"[EXTRACT_USER_CONTENT 8.0] secret_name = {secret_name}")

        try:
            response = _secrets_client.get_secret_value(SecretId=secret_name)

            logger.info(f"[EXTRACT_USER_CONTENT 8.1] response = {response}")

            _jwt_secret_cache = json.loads(response['SecretString'])['secret']

            logger.info(f"[EXTRACT_USER_CONTENT 9.0] before get headers _jwt_secret_cache= {_jwt_secret_cache}")
        except Exception as e:
            # Fall back to env var for local/dev
        
            logger.error(f"[EXTRACT_USER_CONTENT 9.0Bad] Secrets Manager failed: {str(e)}")
            _jwt_secret_cache = os.environ.get('JWT_SECRET', 'CHANGE-ME-BEFORE-PROD')

    return _jwt_secret_cache


def extract_user_context(event):
    """
    Validates the Bearer token from the Authorization header and returns
    a verified user context dict, or a 401 response dict if invalid.

    Usage in a handler:
        result = extract_user_context(event)
        if isinstance(result, dict) and result.get('statusCode'):
            return result   # early exit — 401
        user_context = result

    Returns on success:
        {
            'user_key':      str,
            'customer_id':   str,
            'username':      str,
            'is_super_user': bool
        }

    Returns on failure:
        A ready-to-return API Gateway response dict with statusCode 401.
    """


    logger.info ('[EXTRACT_USER_CONTENT LAMBDA_UTILS.py] extract_user_context() LOG_START   ')
    ##logger.info(f"EXTRACT_USER_CONTENT LAMBDA_UTILS.py LOG_Event: {json.dumps(event, default=decimal_default)}")

    # try:
    #     #from jwt.api_jwt import PyJWT, decode, decode_complete, encode
    #     logger.info(f"[JWT] import attempt")
    #     import jwt
    #     logger.info(f"[JWT] imported")
    # except ImportError:
    #     jwt = None
    #     logger.info(f"[JWT] NOT imported")
    
    JWT_SECRET = _get_jwt_secret()
    logger.info(f"[EXTRACT_USER_CONTENT 0.0] before get headers JWT_SECRET= {JWT_SECRET}")

    if jwt is None:
        logger.info(f"[JWT] wasn't imported")
        return _auth_error("JWT module not available")
    
    print(f'[EXTRACT_USER_CONTENT] JWT_SECRET=  {JWT_SECRET}')

    logger.info(f"[EXTRACT_USER_CONTENT 0.0b] before get headers")

    headers = event.get('headers', {})

    logger.info(f"[EXTRACT_USER_CONTENT 0.1] before get authorization from headers")
    auth_header = headers.get('authorization') or headers.get('Authorization')

    logger.info(f"[EXTRACT_USER_CONTENT 0.2] Authorization header present: {auth_header is not None}")
    logger.info(f"[EXTRACT_USER_CONTENT 1.0] Raw header value: {auth_header}")        # REMOVE — exposes token

    if not auth_header or not auth_header.startswith('Bearer '):
        ##logger.warning("[JWT] Missing or malformed Authorization header")
        return _auth_error("Missing or invalid Authorization header")

    token = auth_header.split(' ', 1)[1]
    logger.info(f"[EXTRACT_USER_CONTENT 1.1] Token extracted, length: {len(token)}")
    logger.info(f"[EXTRACT_USER_CONTENT 1.2] Token extracted: {token}")
    try:
        logger.info(f"[EXTRACT_USER_CONTENT 1.3] trying to get payload")

        payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        logger.info(f"[EXTRACT_USER_CONTENT 1.4] trying to get payload")
        logger.info(f"[EXTRACT_USER_CONTENT 1.5] payload: {payload}")
        logger.info(f"[EXTRACT_USER_CONTENT 1.6] trying to get payload")

        logger.info(f"[EXTRACT_USER_CONTENT 2.0] get user_key ") 
        logger.info(f"[EXTRACT_USER_CONTENT 2.1] user_key {payload.get('user_key')}") 

        uk = payload.get('user_key')
        logger.info(f"[EXTRACT_USER_CONTENT 2.2] user_key {uk}") 

        logger.info(f"[EXTRACT_USER_CONTENT 2.3] Got payload")
        logger.info(f"[EXTRACT_USER_CONTENT 2.4] user_key {payload.get('user_key')}") 

        ##logger.info(f"[EXTRACT_USER_CONTENT] Decode successful — user_key: {payload.get('user_key')}, "
        ##            f"customer_id: {payload.get('customer_id')}, "
        ##            f"is_super_user: {payload.get('is_super_user')}, "
        ##            f"exp: {payload.get('exp')}")               # REMOVE — exposes identity
        
        ##logger.info(f"[EXTRACT_USER_CONTENT] roles {payload.get('roles')}") 

    except jwt.ExpiredSignatureError:
        logger.warning("[EXTRACT_USER_CONTENT 4.0] Token rejected — expired")
        return _auth_error("Token has expired")
    except jwt.InvalidTokenError as e2:
        logger.warning(f"[EXTRACT_USER_CONTENT 4.1] Token rejected — invalid: {str(e2)}")
        return _auth_error("Invalid token")


    logger.info ('[LAMBDA_UTILS.py] extract_user_context LOG_END   ')

    return {
        'user_key':      payload.get('user_key'),
        'customer_id':   payload.get('customer_id'),
        'username':      payload.get('username'),
        'is_super_user': payload.get('is_super_user', False)
    }



def _auth_error(message):
    """Builds a 401 response in the standard VFE format."""
    import json
    from datetime import datetime
    return {
        'statusCode': 401,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
        },
        'body': json.dumps({
            'success': False,
            'error': message,
            'timestamp': datetime.utcnow().isoformat()
        })
    }