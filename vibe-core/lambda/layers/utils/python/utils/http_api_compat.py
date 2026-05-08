# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
HTTP API Event Compatibility Helper
Handles event structure differences between REST API and HTTP API
"""
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def normalize_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize event structure to work with both REST API (v1) and HTTP API (v2) formats
    
    HTTP API (v2) structure:
    {
        "version": "2.0",
        "routeKey": "POST /items",
        "rawPath": "/items",
        "requestContext": {
            "http": {
                "method": "POST",
                "path": "/items"
            }
        },
        "body": "...",
        "pathParameters": {...},
        "queryStringParameters": {...},
        "headers": {...}
    }
    
    REST API (v1) structure:
    {
        "httpMethod": "POST",
        "path": "/items",
        "pathParameters": {...},
        "queryStringParameters": {...},
        "headers": {...},
        "body": "..."
    }
    """
    normalized = event.copy()
    
    # Detect HTTP API v2 format
    if event.get('version') == '2.0' or 'requestContext' in event and 'http' in event.get('requestContext', {}):
        logger.info("Detected HTTP API (v2) event format")
        
        # Extract HTTP method from requestContext
        if 'requestContext' in event and 'http' in event['requestContext']:
            http_context = event['requestContext']['http']
            normalized['httpMethod'] = http_context.get('method', '')
            
            # Preserve path
            if 'path' not in normalized:
                normalized['path'] = http_context.get('path', '')
    
    # Ensure httpMethod exists (for backwards compatibility)
    if 'httpMethod' not in normalized:
        normalized['httpMethod'] = event.get('requestContext', {}).get('http', {}).get('method', 'GET')
    
    # Ensure headers exist
    if 'headers' not in normalized:
        normalized['headers'] = {}
    
    # Ensure pathParameters exist
    if 'pathParameters' not in normalized:
        normalized['pathParameters'] = {}
    
    # Ensure queryStringParameters exist
    if 'queryStringParameters' not in normalized:
        normalized['queryStringParameters'] = {}
    
    logger.info(f"Normalized event - Method: {normalized.get('httpMethod')}, Path: {normalized.get('path')}")
    
    return normalized


def get_http_method(event: Dict[str, Any]) -> str:
    """Get HTTP method from either REST API or HTTP API event"""
    normalized = normalize_event(event)
    return normalized.get('httpMethod', 'GET')


def get_path_parameter(event: Dict[str, Any], param_name: str) -> Optional[str]:
    """Get path parameter from either REST API or HTTP API event"""
    normalized = normalize_event(event)
    return normalized.get('pathParameters', {}).get(param_name)


def get_query_parameter(event: Dict[str, Any], param_name: str, default: Optional[str] = None) -> Optional[str]:
    """Get query parameter from either REST API or HTTP API event"""
    normalized = normalize_event(event)
    return normalized.get('queryStringParameters', {}).get(param_name, default)


def get_header(event: Dict[str, Any], header_name: str, default: Optional[str] = None) -> Optional[str]:
    """Get header from either REST API or HTTP API event (case-insensitive)"""
    normalized = normalize_event(event)
    headers = normalized.get('headers', {})
    
    # HTTP API headers are lowercase by default
    header_name_lower = header_name.lower()
    
    # Try exact match first
    if header_name in headers:
        return headers[header_name]
    
    # Try lowercase match
    if header_name_lower in headers:
        return headers[header_name_lower]
    
    # Try case-insensitive search
    for key, value in headers.items():
        if key.lower() == header_name_lower:
            return value
    
    return default


def get_body(event: Dict[str, Any]) -> Optional[str]:
    """Get request body from either REST API or HTTP API event"""
    normalized = normalize_event(event)
    body = normalized.get('body')
    
    # HTTP API automatically decodes base64 if needed
    if body and normalized.get('isBase64Encoded'):
        import base64
        body = base64.b64decode(body).decode('utf-8')
    
    return body


def parse_json_body(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Parse JSON body from either REST API or HTTP API event"""
    body = get_body(event)
    
    if not body:
        return None
    
    if isinstance(body, dict):
        return body
    
    try:
        return json.loads(body)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON body: {str(e)}")
        return None


# Example usage in Lambda handler
def example_lambda_handler(event, context):
    """
    Example Lambda handler showing how to use the compatibility helper
    """
    # Normalize the event for compatibility
    normalized_event = normalize_event(event)
    
    # Get HTTP method (works with both REST and HTTP API)
    http_method = get_http_method(event)
    
    # Handle OPTIONS for CORS (HTTP API handles this automatically, but keeping for safety)
    if http_method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization'
            },
            'body': ''
        }
    
    # Get path parameters
    customer_id = get_path_parameter(event, 'customer_id')
    user_key = get_path_parameter(event, 'user_key')
    
    # Get query parameters
    page = get_query_parameter(event, 'page', '1')
    limit = get_query_parameter(event, 'limit', '10')
    
    # Get headers
    authorization = get_header(event, 'Authorization')
    content_type = get_header(event, 'Content-Type')
    
    # Parse JSON body
    body_data = parse_json_body(event)
    
    # Your business logic here
    result = {
        'method': http_method,
        'customer_id': customer_id,
        'user_key': user_key,
        'page': page,
        'limit': limit,
        'has_auth': authorization is not None,
        'body_data': body_data
    }
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(result)
    }