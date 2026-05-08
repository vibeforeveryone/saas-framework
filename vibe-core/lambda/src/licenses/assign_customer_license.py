# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
import json
import boto3
import os
from utils.http_api_compat import normalize_event, get_http_method, parse_json_body
import logging
from datetime import datetime
from utils.cors_utils import create_response
from utils.guid_utils import generate_guid
from boto3.dynamodb.conditions import Key
from utils.track_api_call import tracked

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

dynamodb = boto3.resource('dynamodb')
history_table = dynamodb.Table(
    os.environ.get('CUSTOMER_LICENSE_HISTORY_TABLE', 'CustomerLicenseHistory'))
license_table = dynamodb.Table(os.environ.get('LICENSE_TABLE', 'License'))

VALID_CHANGED_BY_TYPES = ['customer_self_service', 'super_user', 'public_signup']


@tracked
def lambda_handler(event, context):
    """
    Assign or change a customer's license.

    Steps:
      1. Validate the incoming license_key exists and is active.
      2. Find and close the current active history row (set end_date = now).
      3. Write a new history row with end_date = 'active'.

    Body:
      {
        "license_key": "abc-123",
        "changed_by_user_key": "user-xyz",
        "changed_by_type": "customer_self_service" | "super_user" | "public_signup"
      }

    The public_signup path calls this same function but passes
    changed_by_type='public_signup'. The complete_public_signup.py
    Lambda also writes directly to this table in its transaction —
    this endpoint is for post-signup license changes.
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

        body = parse_json_body(event)
        if not body:
            return create_response(400, False, error="Request body is required")

        new_license_key = body.get('license_key')
        changed_by_user_key = body.get('changed_by_user_key', user_id)
        changed_by_type = body.get('changed_by_type', 'customer_self_service')

        if not new_license_key:
            return create_response(400, False, error="license_key is required")

        if changed_by_type not in VALID_CHANGED_BY_TYPES:
            return create_response(400, False,
                error=f"changed_by_type must be one of: {', '.join(VALID_CHANGED_BY_TYPES)}")

        logger.info(f"Assign customer license - customer: {customer_id} "
                    f"license: {new_license_key} by: {changed_by_user_key} "
                    f"type: {changed_by_type}")

        # --- Step 1: Validate the new license exists and is active ---
        lic_response = license_table.get_item(Key={'license_key': new_license_key})
        if 'Item' not in lic_response:
            return create_response(404, False,
                error=f"License not found: {new_license_key}")

        new_license = lic_response['Item']
        if not new_license.get('is_active', False):
            return create_response(400, False,
                error="Cannot assign an inactive license. "
                      "Please select an active license.")

        now = datetime.utcnow().isoformat()

        # --- Step 2: Close the current active history row if one exists ---
        existing = history_table.query(
            IndexName='customer_id-end_date-index',
            KeyConditionExpression=(
                Key('customer_id').eq(customer_id) &
                Key('end_date').eq('active')
            )
        )
        current_rows = existing.get('Items', [])

        if current_rows:
            # Guard: close all active rows (should be exactly one, but be safe)
            for row in current_rows:
                if row.get('license_key') == new_license_key:
                    # Already on this license — nothing to do
                    logger.info(f"Customer {customer_id} already on license {new_license_key}")
                    return create_response(200, True, {
                        'message': 'Customer is already on this license',
                        'license_key': new_license_key
                    })
                history_table.update_item(
                    Key={'history_key': row['history_key']},
                    UpdateExpression='SET end_date = :end_date',
                    ExpressionAttributeValues={':end_date': now}
                )
                logger.info(f"Closed history row {row['history_key']} end_date={now}")

        # --- Step 3: Write new active history row ---
        new_history_key = generate_guid()
        new_row = {
            'history_key': new_history_key,
            'customer_id': customer_id,
            'license_key': new_license_key,
            'effective_date': now,
            'end_date': 'active',             # Sentinel for current active license
            'changed_by_user_key': changed_by_user_key,
            'changed_by_type': changed_by_type,
            'created_at': now,
        }
        history_table.put_item(Item=new_row)
        logger.info(f"Created new history row {new_history_key} for customer {customer_id}")

        return create_response(200, True, {
            'history_key': new_history_key,
            'customer_id': customer_id,
            'license_key': new_license_key,
            'effective_date': now,
            'message': 'License assigned successfully'
        })

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return create_response(400, False, error="Invalid JSON in request body")
    except Exception as e:
        logger.error(f"Error assigning customer license: {str(e)}")
        import traceback
        traceback.print_exc()
        return create_response(500, False,
            error=f"Failed to assign customer license: {str(e)}")
