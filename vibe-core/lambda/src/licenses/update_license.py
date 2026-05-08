# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Update License
Updates a system-wide license tier (superuser only).
PUT /licenses/{license_key}
Supports partial updates — only fields present in the body are changed.
is_active can be set to false to retire a tier without deleting it.
"""
import json
import boto3
import os
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from utils.cors_utils import create_response
from utils.track_api_call import tracked
from utils.lambda_utils import extract_user_context

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

dynamodb = boto3.resource('dynamodb')
license_table = dynamodb.Table('License')


@tracked
def lambda_handler(event, context):
    """
    Update a license tier.
    PUT /licenses/{license_key}
    Body (all optional): { tier_desc, min_users, max_users, monthly_cost,
                           discount_percentage, is_active }
    """
    logger.info(f"Event: {json.dumps(event)}")

    try:
        http_method = event.get('requestContext', {}).get('http', {}).get('method')
        if http_method == 'OPTIONS':
            return create_response(200, True)

        user_context = extract_user_context(event)
        logger.info(f"User context: {json.dumps(user_context)}")

        if not user_context.get('is_super_user'):
            return create_response(403, False, error="Superuser access required")

        path_params = event.get('pathParameters', {})
        license_key = path_params.get('license_key')
        if not license_key:
            return create_response(400, False, error="Missing license_key in path")

        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})

        # Confirm record exists
        existing = license_table.get_item(Key={'license_key': license_key})
        if 'Item' not in existing:
            return create_response(404, False, error=f"License not found: {license_key}")

        current = existing['Item']
        user_id = user_context.get('user_id', 'system')

        # ── Build update expression — only fields present in body ─────
        update_expression = "SET modified_at = :modified_at, modified_by = :modified_by"
        expression_values = {
            ':modified_at': datetime.utcnow().isoformat(),
            ':modified_by': user_id,
        }

        if 'tier_desc' in body:
            if len(str(body['tier_desc'])) > 100:
                return create_response(400, False, error="tier_desc must be 100 characters or less")
            update_expression += ", tier_desc = :tier_desc"
            expression_values[':tier_desc'] = body['tier_desc']

        if 'min_users' in body:
            try:
                min_users = int(body['min_users'])
                if min_users < 0:
                    return create_response(400, False, error="min_users must be >= 0")
                update_expression += ", min_users = :min_users"
                expression_values[':min_users'] = min_users
            except (ValueError, TypeError):
                return create_response(400, False, error="min_users must be a valid integer")

        if 'max_users' in body:
            try:
                max_users = int(body['max_users'])
                # Validate against the effective min_users (updated or existing)
                effective_min = expression_values.get(':min_users',
                                    current.get('min_users', 0))
                if max_users < effective_min:
                    return create_response(400, False, error="max_users must be >= min_users")
                update_expression += ", max_users = :max_users"
                expression_values[':max_users'] = max_users
            except (ValueError, TypeError):
                return create_response(400, False, error="max_users must be a valid integer")

        if 'monthly_cost' in body:
            try:
                monthly_cost = Decimal(str(body['monthly_cost']))
                if monthly_cost < 0:
                    return create_response(400, False, error="monthly_cost must be >= 0")
                update_expression += ", monthly_cost = :monthly_cost"
                expression_values[':monthly_cost'] = monthly_cost
            except (InvalidOperation, TypeError):
                return create_response(400, False, error="monthly_cost must be a valid number")

        if 'discount_percentage' in body:
            try:
                discount = Decimal(str(body['discount_percentage']))
                if discount < 0 or discount > 100:
                    return create_response(400, False,
                        error="discount_percentage must be between 0 and 100")
                update_expression += ", discount_percentage = :discount_percentage"
                expression_values[':discount_percentage'] = discount
            except (InvalidOperation, TypeError):
                return create_response(400, False,
                    error="discount_percentage must be a valid number")

        if 'is_active' in body:
            # Accept both boolean True/False and string "true"/"false"
            raw = body['is_active']
            if isinstance(raw, bool):
                is_active = raw
            elif isinstance(raw, str):
                is_active = raw.lower() == 'true'
            else:
                return create_response(400, False, error="is_active must be true or false")
            update_expression += ", is_active = :is_active"
            expression_values[':is_active'] = is_active

        response = license_table.update_item(
            Key={'license_key': license_key},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values,
            ReturnValues='ALL_NEW'
        )

        updated = response['Attributes']
        logger.info(f"Updated license: {license_key}")

        return create_response(200, True, {
            'license': updated,
            'message': 'License tier updated successfully'
        })

    except json.JSONDecodeError:
        return create_response(400, False, error="Invalid JSON in request body")
    except Exception as e:
        logger.error(f"Error updating license: {str(e)}")
        import traceback
        traceback.print_exc()
        return create_response(500, False, error=f"Failed to update license: {str(e)}")
