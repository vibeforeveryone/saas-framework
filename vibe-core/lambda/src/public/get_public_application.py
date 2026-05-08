# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Get Public Application Details
Public API to get application details including pricing and features
No authentication required
Supports AWS API Gateway V2
"""
import json
import boto3
import traceback
from datetime import datetime
from decimal import Decimal
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
APPLICATION_TABLE = dynamodb.Table('Application')
LICENSE_TABLE = dynamodb.Table('License')
API_RATE_TABLE = dynamodb.Table('APIRate')
FLAT_BASE_RATE_TABLE = dynamodb.Table('FlatBaseRate')
FEATURE_TABLE = dynamodb.Table('Feature')

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
    Public API: Get application details including pricing and features
    GET /public/applications/{app_key}
    
    No authentication required
    Returns detailed information for active applications only
    """
    print(f"Event: {json.dumps(event, default=decimal_default)}")
    print(f"Context: {context}")
    
    try:
        http_method = event.get('requestContext', {}).get('http', {}).get('method')
        
        if http_method == 'OPTIONS':
            return create_response(200, True)
        
        # Get path parameters
        path_params = event.get('pathParameters', {})
        app_key = path_params.get('app_key')
        
        if not app_key:
            return create_response(400, False, error="Missing app_key in path")
        
        print(f"Getting public application: {app_key}")
        
        # Get application
        response = APPLICATION_TABLE.get_item(Key={'app_key': app_key})
        
        if 'Item' not in response:
            return create_response(404, False, error=f"Application not found: {app_key}")
        
        app = response['Item']
        
        # Only return if active
        if app.get('status') != 'active':
            return create_response(404, False, error="Application not available")
        
        # Build public response
        public_app = {
            'app_key': app.get('app_key'),
            'app_name': app.get('app_name'),
            'app_desc': app.get('app_desc'),
            'website': app.get('website'),
            'billing_model': app.get('billing_model')
        }
        
        # Get pricing based on billing model
        if app.get('billing_model') == 'BillByUser':
            print(f"Getting license tiers for {app_key}")
            
            # Get license tiers
            response = LICENSE_TABLE.query(
                IndexName='app_key-tier_desc-index',
                KeyConditionExpression=Key('app_key').eq(app_key)
            )
            licenses = response.get('Items', [])
            licenses = sorted(licenses, key=lambda x: x.get('min_users', 0))
            
            public_app['license_tiers'] = [
                {
                    'license_key': lic.get('license_key'),
                    'tier_desc': lic.get('tier_desc'),
                    'min_users': lic.get('min_users'),
                    'max_users': lic.get('max_users'),
                    'monthly_cost': float(lic.get('monthly_cost', 0)),
                    'discount_percentage': float(lic.get('discount_percentage', 0))
                }
                for lic in licenses
            ]
        
        elif app.get('billing_model') == 'BillByTransactions':
            print(f"Getting API rate tiers for {app_key}")
            
            # Get API rate tiers
            response = API_RATE_TABLE.query(
                KeyConditionExpression=Key('app_key').eq(app_key)
            )
            api_rates = response.get('Items', [])
            api_rates = sorted(api_rates, key=lambda x: x.get('seq', 0))
            
            public_app['api_rate_tiers'] = [
                {
                    'seq': rate.get('seq'),
                    'range_start': rate.get('range_start'),
                    'range_max': rate.get('range_max'),
                    'price_per_transaction': float(rate.get('price_per_transaction', 0))
                }
                for rate in api_rates
            ]
            
            # Get flat base rate
            response = FLAT_BASE_RATE_TABLE.get_item(Key={'app_key': app_key})
            if 'Item' in response:
                public_app['flat_base_rate'] = float(response['Item'].get('flat_base_rate', 0))
            else:
                public_app['flat_base_rate'] = 0.0
        
        # Get available features
        print(f"Getting features for {app_key}")
        response = FEATURE_TABLE.query(
            IndexName='app_key-feature_desc-index',
            KeyConditionExpression=Key('app_key').eq(app_key)
        )
        features = response.get('Items', [])
        features = sorted(features, key=lambda x: x.get('feature_desc', ''))
        
        public_app['features'] = [
            {
                'feature_key': feat.get('feature_key'),
                'feature_desc': feat.get('feature_desc')
            }
            for feat in features
        ]
        
        print(f"Retrieved public application details: {app_key}")
        
        return create_response(200, True, {
            'application': public_app
        })
        
    except Exception as e:
        print(f"Error getting public application: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to get application: {str(e)}")
