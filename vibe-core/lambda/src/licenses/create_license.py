# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Create License
Creates a system-wide license tier (superuser only).
Licenses are no longer tied to an application.
POST /licenses
"""
import json
import boto3
import os
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from utils.cors_utils import create_response
from utils.guid_utils import generate_guid
from utils.track_api_call import tracked

from utils.lambda_utils import extract_user_context, decimal_default

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

dynamodb = boto3.resource('dynamodb')
license_table = dynamodb.Table('License')


@tracked
def lambda_handler(event, context):
    """
    Create a new license tier.
    POST /licenses
    Body: { tier_desc, min_users, max_users, monthly_cost, discount_percentage? }
    """
    logger.info(f"Event: {json.dumps(event)}")

    try:
        http_method = event.get('requestContext', {}).get('http', {}).get('method')
        if http_method == 'OPTIONS':
            return create_response(200, True)

        user_context = extract_user_context(event)
        logger.info(f"CREATE_LICENSE User context: {json.dumps(user_context)}")

        if not user_context.get('is_super_user'):
            return create_response(403, False, error="Superuser access required")

        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})

        # ── Validation ────────────────────────────────────────────────
        required = ['tier_desc', 'min_users', 'max_users', 'monthly_cost']
        for field in required:
            if field not in body or body[field] == '' or body[field] is None:
                return create_response(400, False, error=f"Missing required field: {field}")

        if len(str(body['tier_desc'])) > 100:
            return create_response(400, False, error="tier_desc must be 100 characters or less")

        try:
            min_users = int(body['min_users'])
            if min_users < 0:
                return create_response(400, False, error="min_users must be >= 0")
        except (ValueError, TypeError):
            return create_response(400, False, error="min_users must be a valid integer")

        try:
            max_users = int(body['max_users'])
            if max_users < min_users:
                return create_response(400, False, error="max_users must be >= min_users")
        except (ValueError, TypeError):
            return create_response(400, False, error="max_users must be a valid integer")

        try:
            monthly_cost = Decimal(str(body['monthly_cost']))
            if monthly_cost < 0:
                return create_response(400, False, error="monthly_cost must be >= 0")
        except (InvalidOperation, TypeError):
            return create_response(400, False, error="monthly_cost must be a valid number")

        try:
            discount_percentage = Decimal(str(body.get('discount_percentage', 0)))
            if discount_percentage < 0 or discount_percentage > 100:
                return create_response(400, False, error="discount_percentage must be between 0 and 100")
        except (InvalidOperation, TypeError):
            return create_response(400, False, error="discount_percentage must be a valid number")

        # ── Build record ──────────────────────────────────────────────
        license_key   = generate_guid()
        current_time  = datetime.utcnow().isoformat()
        user_id       = user_context.get('user_id', 'system')

        license = {
            'license_key':          license_key,
            'tier_desc':            body['tier_desc'],
            'min_users':            min_users,
            'max_users':            max_users,
            'monthly_cost':         monthly_cost,
            'discount_percentage':  discount_percentage,
            'is_active':            True,          # always active on creation
            'created_at':           current_time,
            'modified_at':          current_time,
            'created_by':           user_id,
            'modified_by':          user_id,
        }

        license_table.put_item(Item=license)
        logger.info(f"Created license: {license_key} ({body['tier_desc']})")

        return create_response(201, True, {
            'license': license,
            'message': 'License tier created successfully'
        })

    except json.JSONDecodeError:
        return create_response(400, False, error="Invalid JSON in request body")
    except Exception as e:
        logger.error(f"Error creating license: {str(e)}")
        import traceback
        traceback.print_exc()
        return create_response(500, False, error=f"Failed to create license: {str(e)}")
