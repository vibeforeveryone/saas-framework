# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Logout
Revokes the refresh token in DynamoDB and clears the httpOnly cookie.
Requires a valid Authorization: Bearer <access_token> header.

POST /auth/logout
"""
import json
import boto3
import os
import traceback
import logging
from datetime import datetime

from utils.lambda_utils import decimal_default

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

try:
    import jwt
except ImportError:
    logger.warning("WARNING: jwt module not available")
    jwt = None

# ── AWS clients ───────────────────────────────────────────────────────────────
dynamodb       = boto3.resource('dynamodb')
secrets_client = boto3.client('secretsmanager')

REFRESH_TOKENS_TABLE = dynamodb.Table(os.environ.get('REFRESH_TOKENS_TABLE', 'RefreshTokens'))

# ── Config ─────────────────────────────────────────────────────────────────────
ALLOWED_ORIGIN = os.environ.get('ALLOWED_ORIGIN', 'http://localhost:3000')
ENVIRONMENT    = os.environ.get('ENVIRONMENT', 'dev')

# ── JWT secret — cached per cold start ────────────────────────────────────────
_jwt_secret = None


#this get_jwt_secret() in logout and refresh_token is different than Auth, and needs to be reviewed as it is brought back into play
def get_jwt_secret():
    global _jwt_secret
    if _jwt_secret is None:
        response    = secrets_client.get_secret_value(SecretId='vfeVer1/jwt-access-secret')
        _jwt_secret = json.loads(response['SecretString'])['secret']
    return _jwt_secret

#temporary replacement
# def get_jwt_secret():
#     global _jwt_secret
#     if _jwt_secret is None:
#         # TODO: Re-enable Secrets Manager before production deployment
#         # response   = secrets_client.get_secret_value(SecretId='vfeVer1/jwt-access-secret')
#         # _jwt_secret = json.loads(response['SecretString'])['secret']
#         _jwt_secret = os.environ.get('JWT_SECRET', 'CHANGE-ME-BEFORE-PROD')
#     return _jwt_secret

# ── Cookie / response helpers ──────────────────────────────────────────────────
def clear_cookie():
    """Return a Set-Cookie value that immediately expires the refresh_token cookie."""
    return "refresh_token=; HttpOnly; Path=/auth; Max-Age=0; SameSite=Strict"


def logout_response(status_code, success, data=None, error=None, clear_refresh_cookie=False):
    body = {
        'success':   success,
        'data':      data,
        'error':     error,
        'timestamp': datetime.utcnow().isoformat()
    }
    response = {
        'statusCode': status_code,
        'headers': {
            'Content-Type':                    'application/json',
            'Access-Control-Allow-Origin':      ALLOWED_ORIGIN,
            'Access-Control-Allow-Credentials': 'true',
            'Access-Control-Allow-Headers': (
                'Content-Type,X-Amz-Date,Authorization,X-Api-Key,'
                'X-Amz-Security-Token,X-User-Id,X-Customer-Id'
            ),
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
        },
        'body': json.dumps(body, default=decimal_default)
    }
    if clear_refresh_cookie:
        response['cookies'] = [clear_cookie()]
    return response


def extract_refresh_token_from_event(event):
    """Extract refresh_token value from cookie."""
    cookies = event.get('cookies', [])
    for cookie in cookies:
        if cookie.strip().startswith('refresh_token='):
            return cookie.split('=', 1)[1].strip()

    headers    = event.get('headers', {})
    cookie_hdr = headers.get('cookie') or headers.get('Cookie', '')
    if cookie_hdr:
        for part in cookie_hdr.split(';'):
            part = part.strip()
            if part.startswith('refresh_token='):
                return part.split('=', 1)[1].strip()
    return None


def extract_access_token(event):
    """Extract Bearer token from Authorization header."""
    headers = event.get('headers', {})
    auth    = headers.get('authorization') or headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        return auth[7:].strip()
    return None


def verify_access_token(token):
    """
    Verify the access token signature and expiry.
    Returns (True, payload) or (False, error_message).
    Accepts expired tokens for logout — we still want to allow logout
    even if the access token has just expired.
    """
    if jwt is None:
        return True, {}   # If JWT module missing, allow logout to proceed
    try:
        jwt_secret = get_jwt_secret()
        payload = jwt.decode(token, jwt_secret, algorithms=['HS256'])
        return True, payload
    except jwt.ExpiredSignatureError:
        # Allow logout even with expired access token
        try:
            payload = jwt.decode(
                token, jwt_secret, algorithms=['HS256'],
                options={"verify_exp": False}
            )
            return True, payload
        except Exception:
            return True, {}
    except jwt.InvalidTokenError as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)


# ── Handler ────────────────────────────────────────────────────────────────────
def lambda_handler(event, context):
    """
    POST /auth/logout
    Revokes the refresh token in DynamoDB and clears the cookie.
    """
    logger.info("Logout request received")

    try:
        http_method = event.get('requestContext', {}).get('http', {}).get('method', '')
        if http_method == 'OPTIONS':
            return logout_response(200, True)

        # ── Validate access token ─────────────────────────────────────────────
        access_token = extract_access_token(event)
        if not access_token:
            logger.warning("LO1 No access token on logout request")
            # Still clear the cookie even without a valid access token
            return logout_response(
                401, False,
                error="Unauthorized",
                clear_refresh_cookie=True
            )

        valid, payload = verify_access_token(access_token)
        if not valid:
            logger.warning(f"LO2 Invalid access token on logout: {payload}")
            return logout_response(
                401, False,
                error="Unauthorized",
                clear_refresh_cookie=True
            )

        user_key = payload.get('user_key', 'unknown') if isinstance(payload, dict) else 'unknown'
        logger.info(f"LO3 Logout for user_key: {user_key}")

        # ── Revoke refresh token ──────────────────────────────────────────────
        token_id = extract_refresh_token_from_event(event)

        if token_id:
            try:
                REFRESH_TOKENS_TABLE.update_item(
                    Key={'token_id': token_id},
                    UpdateExpression='SET revoked = :t',
                    ExpressionAttributeValues={':t': True},
                    ConditionExpression='attribute_exists(token_id)'
                )
                logger.info(f"LO4 Refresh token revoked: {token_id[:8]}...")
            except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
                # Token doesn't exist — already expired or already revoked; fine
                logger.info(f"LO5 Refresh token not found (already expired/revoked): {token_id[:8]}...")
            except Exception as e:
                # Non-fatal — still clear the cookie
                logger.error(f"LO6 Error revoking refresh token: {str(e)}")
        else:
            logger.info("LO7 No refresh token cookie present on logout — cookie already cleared")

        logger.info(f"LO8 Logout complete for user_key: {user_key}")

        return logout_response(
            200, True,
            data={'message': 'Logged out successfully'},
            clear_refresh_cookie=True
        )

    except Exception as e:
        logger.error(f"Unexpected error in logout: {str(e)}\n{traceback.format_exc()}")
        # Always clear the cookie even on unexpected errors
        return logout_response(
            500, False,
            error="Logout error",
            clear_refresh_cookie=True
        )
