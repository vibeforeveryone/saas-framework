# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
import json
import boto3
import os
from utils.http_api_compat import normalize_event, get_http_method
import logging
from utils.cors_utils import create_response
from boto3.dynamodb.conditions import Key
from utils.track_api_call import tracked

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

dynamodb = boto3.resource('dynamodb')
history_table = dynamodb.Table(
    os.environ.get('CUSTOMER_LICENSE_HISTORY_TABLE', 'CustomerLicenseHistory'))
license_table = dynamodb.Table(os.environ.get('LICENSE_TABLE', 'License'))


@tracked
def lambda_handler(event, context):
    """
    Return the full license history for a customer, newest first.
    Each row includes the full License definition joined in.
    Used by: customer dashboard history panel, super user admin view,
             and future billing module.

    The current active license is the row where end_date = 'active'.
    Past rows have end_date set to an ISO timestamp.
    """
    event = normalize_event(event)

    try:
        if get_http_method(event) == 'OPTIONS':
            return create_response(200, True)

        headers = event.get('headers', {})
        user_id = (headers.get('X-User-Id') or headers.get('x-user-id') or
                   headers.get('userId') or 'demo-user')
        claims = event.get('requestContext', {}).get('authorizer', {}).get('claims', {})
        if user_id == 'demo-user':
            user_id = claims.get('sub', user_id)

        path_params = event.get('pathParameters', {}) or {}
        customer_id = path_params.get('customer_id')
        if not customer_id:
            return create_response(400, False, error="Missing customer_id in path")

        logger.info(f"Get license history - customer_id: {customer_id} user: {user_id}")

        # Query all history rows for this customer using the effective_date GSI
        response = history_table.query(
            IndexName='customer_id-effective_date-index',
            KeyConditionExpression=Key('customer_id').eq(customer_id),
            ScanIndexForward=False   # newest first
        )
        rows = response.get('Items', [])

        if not rows:
            return create_response(200, True, {
                'history': [],
                'count': 0
            })

        # Collect unique license_keys and batch-fetch license details
        license_keys = list({row['license_key'] for row in rows})
        license_map = {}
        for lk in license_keys:
            lic_response = license_table.get_item(Key={'license_key': lk})
            if 'Item' in lic_response:
                license_map[lk] = lic_response['Item']

        # Join license detail into each history row
        history = []
        for row in rows:
            enriched = {
                **row,
                'license': license_map.get(row['license_key'])
            }
            history.append(enriched)

        logger.info(f"Returning {len(history)} history rows for customer {customer_id}")

        return create_response(200, True, {
            'history': history,
            'count': len(history)
        })

    except Exception as e:
        logger.error(f"Error getting license history: {str(e)}")
        import traceback
        traceback.print_exc()
        return create_response(500, False,
            error=f"Failed to get license history: {str(e)}")
