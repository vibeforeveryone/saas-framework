# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
List Licenses
Returns all system-wide license tiers.
Supports optional filtering by active status.

GET /licenses              → all licenses (active + inactive)
GET /licenses?active=true  → active licenses only
GET /licenses?active=false → inactive licenses only
"""
import json
import boto3
import os
import logging
from utils.cors_utils import create_response
from utils.track_api_call import tracked
from utils.lambda_utils import extract_user_context

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

dynamodb = boto3.resource('dynamodb')
license_table = dynamodb.Table('License')


@tracked
def lambda_handler(event, context):
    logger.info(f"Event: {json.dumps(event)}")

    try:
        http_method = event.get('requestContext', {}).get('http', {}).get('method')
        if http_method == 'OPTIONS':
            return create_response(200, True)

        user_context = extract_user_context(event)
        logger.info(f"User context: {json.dumps(user_context)}")

        # Parse optional ?active= query parameter
        query_params = event.get('queryStringParameters') or {}
        active_param = query_params.get('active', None)

        # Scan — license list is small (tens of records at most)
        response = license_table.scan()
        licenses = response.get('Items', [])

        while 'LastEvaluatedKey' in response:
            response = license_table.scan(
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            licenses.extend(response.get('Items', []))

        # Apply active filter if requested
        if active_param is not None:
            filter_active = active_param.lower() == 'true'
            licenses = [
                lic for lic in licenses
                # Treat missing is_active as True (legacy records created before
                # the field was introduced are assumed to be active)
                if lic.get('is_active', True) == filter_active
            ]

        # Sort alphabetically by tier_desc
        licenses = sorted(licenses, key=lambda x: x.get('tier_desc', '').lower())

        logger.info(
            f"Retrieved {len(licenses)} license(s) "
            f"(active filter: {active_param})"
        )

        return create_response(200, True, {
            'licenses': licenses,
            'count': len(licenses),
            'active_filter': active_param,
        })

    except Exception as e:
        logger.error(f"Error listing licenses: {str(e)}")
        import traceback
        traceback.print_exc()
        return create_response(500, False, error=f"Failed to list licenses: {str(e)}")
