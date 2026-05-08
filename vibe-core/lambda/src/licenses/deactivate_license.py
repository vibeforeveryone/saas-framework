# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
import json
import boto3
import os
from utils.http_api_compat import normalize_event, get_http_method
import logging
from datetime import datetime
from utils.cors_utils import create_response
from utils.track_api_call import tracked

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

dynamodb = boto3.resource('dynamodb')
license_table = dynamodb.Table(os.environ.get('LICENSE_TABLE', 'License'))


@tracked
def lambda_handler(event, context):
    """
    Deactivate a license (super user only).
    Sets is_active=False and is_active_str='false'.
    Does NOT delete the record — existing customers on this license
    are unaffected; only new signups are blocked from selecting it.
    Returns 400 if already inactive.
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
        license_key = path_params.get('license_key')
        if not license_key:
            return create_response(400, False, error="Missing license_key in path")

        existing = license_table.get_item(Key={'license_key': license_key})
        if 'Item' not in existing:
            return create_response(404, False, error=f"License not found: {license_key}")

        current = existing['Item']
        if not current.get('is_active', True):
            return create_response(400, False,
                error="License is already inactive")

        license_table.update_item(
            Key={'license_key': license_key},
            UpdateExpression=(
                'SET is_active = :is_active, '
                'is_active_str = :is_active_str, '
                'modified_at = :modified_at, '
                'modified_by = :modified_by'
            ),
            ExpressionAttributeValues={
                ':is_active': False,
                ':is_active_str': 'false',
                ':modified_at': datetime.utcnow().isoformat(),
                ':modified_by': user_id,
            }
        )

        logger.info(f"Deactivated license: {license_key} by user {user_id}")

        return create_response(200, True, {
            'license_key': license_key,
            'message': 'License deactivated successfully. Existing customers are unaffected.'
        })

    except Exception as e:
        logger.error(f"Error deactivating license: {str(e)}")
        import traceback
        traceback.print_exc()
        return create_response(500, False, error=f"Failed to deactivate license: {str(e)}")
