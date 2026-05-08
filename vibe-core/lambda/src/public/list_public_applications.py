# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
List Public Applications
Public API to list all available applications for signup
No authentication required
Supports AWS API Gateway V2
"""
import json
import boto3
import traceback
from datetime import datetime
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')
APPLICATION_TABLE = dynamodb.Table('Application')

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

def lambda_handler(event, context):
    """
    Public API: List all available applications for signup
    GET /public/applications
    
    No authentication required
    Returns only active applications with public information
    """
    print(f"Event: {json.dumps(event, default=decimal_default)}")
    print(f"Context: {context}")
    
    try:
        http_method = event.get('requestContext', {}).get('http', {}).get('method')
        
        if http_method == 'OPTIONS':
            return create_response(200, True)
        
        print("Listing public applications")
        
        # Scan all applications
        response = APPLICATION_TABLE.scan()
        applications = response.get('Items', [])
        
        print(f"Found {len(applications)} total applications")
        
        # Filter to only active applications
        applications = [app for app in applications if app.get('status') == 'active']
        
        print(f"Filtered to {len(applications)} active applications")
        
        # Remove internal fields, keep only public info
        public_apps = []
        for app in applications:
            public_app = {
                'app_key': app.get('app_key'),
                'app_name': app.get('app_name'),
                'app_desc': app.get('app_desc'),
                'website': app.get('website'),
                'billing_model': app.get('billing_model')
            }
            public_apps.append(public_app)
        
        # Sort by app_name
        public_apps = sorted(public_apps, key=lambda x: x.get('app_name', ''))
        
        print(f"Returning {len(public_apps)} public applications")
        
        return create_response(200, True, {
            'applications': public_apps,
            'count': len(public_apps)
        })
        
    except Exception as e:
        print(f"Error listing public applications: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to list applications: {str(e)}")
