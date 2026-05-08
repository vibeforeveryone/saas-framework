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
    Get the current active license for a customer.
    Queries CustomerLicenseHistory using the customer_id-end_date-index GSI,
    looking for the row where end_date = 'active'.
    Joins in the full License record so the caller has everything in one trip.
    Returns 404 if the customer has no license assigned yet.
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

        logger.info(f"Get customer license - customer_id: {customer_id} user: {user_id}")

        # Query GSI for the active row (end_date = 'active')
        response = history_table.query(
            IndexName='customer_id-end_date-index',
            KeyConditionExpression=(
                Key('customer_id').eq(customer_id) &
                Key('end_date').eq('active')
            )
        )

        items = response.get('Items', [])
        if not items:
            return create_response(404, False,
                error="No active license found for this customer")

        # Should only ever be one, but guard against data anomalies
        if len(items) > 1:
            logger.warning(f"Multiple active license rows found for customer {customer_id} "
                           f"- using most recent effective_date")
            items.sort(key=lambda x: x.get('effective_date', ''), reverse=True)

        history_row = items[0]

        # Join in the full license definition
        license_response = license_table.get_item(
            Key={'license_key': history_row['license_key']}
        )
        license_detail = license_response.get('Item')

        result = {
            **history_row,
            'license': license_detail
        }

        return create_response(200, True, {
            'customer_license': result
        })

    except Exception as e:
        logger.error(f"Error getting customer license: {str(e)}")
        import traceback
        traceback.print_exc()
        return create_response(500, False, error=f"Failed to get customer license: {str(e)}")
