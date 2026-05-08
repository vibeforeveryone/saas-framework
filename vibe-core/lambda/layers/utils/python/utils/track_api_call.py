# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
track_api_call.py — UtilsLayer module for API call tracking

Place this file in: layers/utils/python/track_api_call.py

Provides two ways to track API calls:

1. DECORATOR (recommended) — wrap lambda_handler for automatic tracking:

    from utils.track_api_call import tracked

    @tracked
    def lambda_handler(event, context):
        ...

2. MANUAL FUNCTION — call explicitly when you need control over what gets tracked:

    from utils.track_api_call import track_api_call

    def lambda_handler(event, context):
        start_time = time.time()
        ...
        response = create_response(200, True, data)
        track_api_call(event, context, response, start_time)
        return response

Both approaches fire an async Lambda.invoke (InvocationType='Event') to the
LogApiCallFunction, which writes the record to ApiCallTrackingTable. The invoke
returns immediately (~5-15ms overhead) and does not block the main response.

Configuration:
    Environment variable LOG_API_CALL_FUNCTION must be set to the function name
    of the tracking Lambda (e.g., "log-api-call"). If missing, tracking is
    silently skipped so the main Lambda is never affected.
"""
import json
import os
import time
import functools
import logging
from datetime import datetime, timezone
from decimal import Decimal

import boto3
import logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# -----------------------------------------------
# Module-level client — reused across warm starts
# -----------------------------------------------
_lambda_client = None

def _get_lambda_client():
    """Lazy-init the Lambda client so cold starts that never track don't pay the cost."""
    global _lambda_client
    if _lambda_client is None:
        _lambda_client = boto3.client('lambda')
    return _lambda_client


def decimal_default(obj):
    """JSON serializer for Decimal objects."""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError


def _extract_user_context(event):
    """Pull tenant identity from API Gateway V2 headers."""
    headers = event.get('headers', {})
    return {
        'user_key': headers.get('x-user-id') or headers.get('X-User-Id') or '',
        'customer_id': headers.get('x-customer-id') or headers.get('X-Customer-Id') or '',
    }


def _extract_request_info(event):
    """Pull HTTP method, path, and route key from the API Gateway V2 event."""
    request_context = event.get('requestContext', {})
    http_info = request_context.get('http', {})
    return {
        'http_method': http_info.get('method', ''),
        'http_path': http_info.get('path', ''),
        'route_key': event.get('routeKey', ''),
        'request_id': request_context.get('requestId', ''),
    }


def _get_request_body_size(event):
    """Estimate the size of the request body in bytes."""
    body = event.get('body')
    if body is None:
        return 0
    if isinstance(body, str):
        return len(body.encode('utf-8'))
    return len(json.dumps(body).encode('utf-8'))


def _get_status_code(response):
    """Extract status code from a Lambda proxy response dict."""
    if isinstance(response, dict):
        return response.get('statusCode', 0)
    return 0


# -----------------------------------------------
# PUBLIC: Manual tracking function
# -----------------------------------------------

def track_api_call(event, context, response, start_time, app_key='', is_billable=True):
    """
    Fire-and-forget async invoke to the tracking Lambda.

    Args:
        event:       The Lambda event dict (from API Gateway)
        context:     The Lambda context object
        response:    The response dict being returned to API Gateway
        start_time:  time.time() captured at the start of the handler
        app_key:     Optional application key for multi-app tracking
        is_billable: Whether this call counts toward billing (default True)
    """
    try:
    
        logger.debug ('TRACK_API_CALL.py track_api_call() LOG_START   ')
        logger.debug(f"LOG_TRACK_API_CALL_Event: {json.dumps(event, default=decimal_default)}")
        logger.debug  ('LOG_FunctionName ' + str(getattr(context, 'function_name', 'unknown')) +' ; funct end of print')


        headers = event.get('headers', {})

        elapsed_ms = str(round((time.time() - start_time) * 1000, 2))
        timestamp = datetime.now(timezone.utc).isoformat()

        # user_ctx = _extract_user_context(event)
     
        # logger.debug  ('LOG_customer_id ' + str(user_ctx['customer_id']) +' ; end of print')
        # logger.debug  ('LOG_user_key ' + str(user_ctx['user_key']) +' ;')


        request_context = event.get('requestContext', {})
     
        ##print(f'LOG API request_id niven1   {request_context.get('requestId', '')}')
    
        payload = {
            'headers': {
                'authorization':  headers.get('authorization') or headers.get('Authorization') or '',
            },
            'function_being_billed' : str(getattr(context, 'function_name', 'unknown')),
            'elapsed_ms': elapsed_ms,
            'timestamp': timestamp,
            'request_id': request_context.get('requestId', '')
        }

        logger.debug(f'TRACK_API_CALL.py LOG Payload payload intermediate test {payload}')
        logger.debug('LOG_Function Name_BEFORE  call invoke log-api-call')

        _get_lambda_client().invoke(
            FunctionName='log-api-call',  #name of lambda being invoked for billing
            # FunctionName=getattr(context, 'function_name', 'unknown'), #function_name,
            InvocationType='Event',        # Fire-and-forget, returns 202 immediately
            Payload=json.dumps(payload, default=decimal_default),
        )

        logger.debug('LOG_FunctionName_AFTER call invoke log-api-call')
        logger.debug ('TRACK_API_CALL.py track_api_call() LOG_END   ')

        

    except Exception as e:
        # Never let tracking errors break the main Lambda
        logger.debug(f"[track_api_call] WARNING — tracking failed (non-fatal): {e}")


# -----------------------------------------------
# PUBLIC: Decorator for automatic tracking
# -----------------------------------------------

def tracked(handler=None, *, app_key='', is_billable=True):
    """
    Decorator that wraps a lambda_handler to automatically track the API call.

    Usage — basic (all defaults):

        @tracked
        def lambda_handler(event, context):
            ...

    Usage — with options:

        @tracked(app_key='my-app', is_billable=False)
        def lambda_handler(event, context):
            ...

    The decorator:
    1. Records the start time
    2. Calls the original handler
    3. Fires the async tracking call with the response status and duration
    4. Returns the original response unchanged

    OPTIONS preflight requests are NOT tracked to avoid billing noise.
    """

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(event, context):
            # Skip tracking for OPTIONS preflight requests

            print ("decorator start")
            http_method = (
                event.get('requestContext', {}).get('http', {}).get('method', '')
                or event.get('httpMethod', '')
            )
            if http_method == 'OPTIONS':
                return fn(event, context)
            
            print ("decorator after options")
            print(f'EVENT INSIDE {event}')
            print(f'context INSIDE {context}')

            start = time.time()
            response = fn(event, context)
            track_api_call(event, context, response, start,
                           app_key=app_key, is_billable=is_billable)
            return response

        return wrapper

    # Support both @tracked and @tracked(...) syntax
    if handler is not None:
        return decorator(handler)
    return decorator
