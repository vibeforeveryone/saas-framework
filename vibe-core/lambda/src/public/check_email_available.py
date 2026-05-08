# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
import json
import boto3
import os
import logging
from datetime import datetime
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.cors_utils import create_response
from boto3.dynamodb.conditions import Key
from utils.track_api_call import tracked

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

dynamodb = boto3.resource('dynamodb')
user_table = dynamodb.Table(os.environ.get('USER_TABLE', 'User'))

@tracked
def lambda_handler(event, context):
    """
    Public API: Check whether an email address is already registered.

    POST /public/check-email
    No authentication required.

    Expected body:
    {
        "email": "user@example.com"
    }

    Returns:
    {
        "available": true/false
    }
    """
    try:
        if event.get('httpMethod') == 'OPTIONS':
            return create_response(200, True)

        logger.info(f"Check email available request: {json.dumps(event)}")

        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})

        # Handle double-serialized body from HTTP API V2
        if isinstance(body, str):
            body = json.loads(body)

        email = (body.get('email') or '').strip().lower()

        if not email:
            return create_response(400, False, error="Email address is required")

        # Basic format check
        if '@' not in email or '.' not in email.split('@')[-1]:
            return create_response(400, False, error="Invalid email address format")

        # Query the GSI to see if any active user already has this email
        response = user_table.query(
            IndexName='user_email-index',
            KeyConditionExpression=Key('user_email').eq(email)
        )

        existing_users = [
            u for u in response.get('Items', [])
            if u.get('status', 'active') == 'active'
        ]

        available = len(existing_users) == 0

        if not available:
            logger.info(f"Email already registered: {email}")
        else:
            logger.info(f"Email available: {email}")

        return create_response(200, True, {
            'available': available,
            'email': email
        })

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return create_response(400, False, error="Invalid JSON in request body")
    except Exception as e:
        logger.error(f"Error in check_email_available: {str(e)}")
        return create_response(500, False, error=f"Failed to check email availability: {str(e)}")
