# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Refresh Token
Validates the httpOnly refresh token cookie, rotates it (single-use),
and returns a fresh 15-minute access token.

POST /auth/refresh
No body required — refresh token arrives via cookie automatically.
"""
import json
import boto3
import os
import traceback
import uuid
from datetime import datetime, timedelta
import logging

from utils.lambda_utils import decimal_default

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

try:
    import jwt
except ImportError:
    logger.warning("WARNING: jwt module not available")
    jwt = None

# ── AWS clients ───────────────────────────────────────────────────────────────
dynamodb        = boto3.resource('dynamodb')
secrets_client  = boto3.client('secretsmanager')

REFRESH_TOKENS_TABLE = dynamodb.Table(os.environ.get('REFRESH_TOKENS_TABLE', 'RefreshTokens'))
USER_TABLE           = dynamodb.Table('User')

# ── Config ────────────────────────────────────────────────────────────────────
ALLOWED_ORIGIN          = os.environ.get('ALLOWED_ORIGIN', 'http://localhost:3000')
ENVIRONMENT             = os.environ.get('ENVIRONMENT', 'dev')
REFRESH_TOKEN_TTL_HOURS = int(os.environ.get('REFRESH_TOKEN_TTL_HOURS', '24'))
ACCESS_TOKEN_MINUTES    = 15

# ── JWT secret — cached per cold start ───────────────────────────────────────
_jwt_secret = None

#this get_jwt_secret() in logout and refresh_token is different than Auth, and needs to be reviewed as it is brought back into play
def get_jwt_secret():
    global _jwt_secret
    if _jwt_secret is None:
        response   = secrets_client.get_secret_value(SecretId='vfeVer1/jwt-access-secret')
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

# ── Cookie helpers ─────────────────────────────────────────────────────────────
def extract_refresh_token_from_event(event):
    """
    HTTP API v2 puts cookies in event['cookies'] as a list of 'name=value' strings.
    Falls back to parsing event['headers']['cookie'] for edge cases.
    """
    # Method 1: event['cookies'] array (HTTP API v2 standard)
    cookies = event.get('cookies', [])
    for cookie in cookies:
        if cookie.strip().startswith('refresh_token='):
            return cookie.split('=', 1)[1].strip()

    # Method 2: raw Cookie header
    headers     = event.get('headers', {})
    cookie_hdr  = headers.get('cookie') or headers.get('Cookie', '')
    if cookie_hdr:
        for part in cookie_hdr.split(';'):
            part = part.strip()
            if part.startswith('refresh_token='):
                return part.split('=', 1)[1].strip()

    return None


def build_refresh_cookie(token_value, clear=False):
    if clear:
        return "refresh_token=; HttpOnly; Path=/auth; Max-Age=0; SameSite=Strict"

    max_age  = REFRESH_TOKEN_TTL_HOURS * 3600
    same_site = "Strict" if ENVIRONMENT == 'prod' else "Lax"
    secure    = "; Secure" if ENVIRONMENT == 'prod' else ""

    return (
        f"refresh_token={token_value}; HttpOnly; Path=/auth;"
        f" Max-Age={max_age}; SameSite={same_site}{secure}"
    )


def refresh_response(status_code, success, data=None, error=None, cookie=None):
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
    if cookie:
        response['cookies'] = [cookie]
    return response


# ── Handler ───────────────────────────────────────────────────────────────────
def lambda_handler(event, context):
    """
    POST /auth/refresh
    Reads refresh_token cookie, validates it, rotates it, returns new access token.
    """
    logger.info("RT refresh request received")

    try:
        http_method = event.get('requestContext', {}).get('http', {}).get('method', '')
        if http_method == 'OPTIONS':
            return refresh_response(200, True)

        # ── Extract cookie ────────────────────────────────────────────────────
        token_id = extract_refresh_token_from_event(event)
        if not token_id:
            logger.warning("RT1 No refresh token cookie present")
            return refresh_response(401, False, error="No refresh token")

        logger.info(f"RT2 Refresh token received: {token_id[:8]}...")

        # ── Load token record from DynamoDB ───────────────────────────────────
        try:
            result = REFRESH_TOKENS_TABLE.get_item(Key={'token_id': token_id})
            token_record = result.get('Item')
        except Exception as e:
            logger.error(f"RT3 DynamoDB error fetching token: {str(e)}")
            return refresh_response(500, False, error="Token validation error")

        if not token_record:
            logger.warning(f"RT4 Token not found: {token_id[:8]}...")
            return refresh_response(401, False, error="Invalid or expired session")

        # ── Validate token ────────────────────────────────────────────────────
        if token_record.get('revoked'):
            logger.warning(f"RT5 REVOKED token reuse attempt: {token_id[:8]}... "
                           f"user_key={token_record.get('user_key')}")
            # Reuse of a revoked token is a theft signal — revoke all sessions
            _revoke_all_user_sessions(token_record.get('user_key'))
            return refresh_response(401, False, error="Session revoked")

        now_epoch = int(datetime.utcnow().timestamp())
        if token_record.get('expires_at', 0) < now_epoch:
            logger.warning(f"RT6 Expired token: {token_id[:8]}...")
            return refresh_response(401, False, error="Session expired — please log in again")

        user_key    = token_record['user_key']
        customer_id = token_record['customer_id']

        logger.info(f"RT7 Token valid for user_key: {user_key}")

        # ── Load current user record (roles may have changed since login) ─────
        try:
            user_result = USER_TABLE.get_item(Key={'user_key': user_key})
            db_user     = user_result.get('Item')
        except Exception as e:
            logger.error(f"RT8 Error fetching user: {str(e)}")
            return refresh_response(500, False, error="Session refresh error")

        if not db_user or db_user.get('status', 'active') != 'active':
            logger.warning(f"RT9 User inactive or not found: {user_key}")
            return refresh_response(401, False, error="Account is not active")

        # ── Rotate refresh token (single-use) ─────────────────────────────────
        new_token_id = str(uuid.uuid4())
        now          = datetime.utcnow()
        new_expires  = int((now + timedelta(hours=REFRESH_TOKEN_TTL_HOURS)).timestamp())

        headers    = event.get('headers', {})
        user_agent = headers.get('user-agent') or headers.get('User-Agent', '')
        ip_address = (
            event.get('requestContext', {})
                 .get('http', {})
                 .get('sourceIp', '')
        )

        try:
            # Mark old token as revoked and point to successor
            REFRESH_TOKENS_TABLE.update_item(
                Key={'token_id': token_id},
                UpdateExpression='SET revoked = :t, replaced_by = :new_id',
                ExpressionAttributeValues={':t': True, ':new_id': new_token_id}
            )

            # Write new token
            REFRESH_TOKENS_TABLE.put_item(Item={
                'token_id':    new_token_id,
                'user_key':    user_key,
                'customer_id': customer_id,
                'created_at':  now.isoformat(),
                'expires_at':  new_expires,
                'revoked':     False,
                'replaced_by': None,
                'user_agent':  user_agent[:500] if user_agent else '',
                'ip_address':  ip_address
            })
            logger.info(f"RT10 Token rotated: {token_id[:8]}... → {new_token_id[:8]}...")

        except Exception as e:
            logger.error(f"RT11 Token rotation error: {str(e)}")
            return refresh_response(500, False, error="Session refresh error")

        # ── Issue new access token ────────────────────────────────────────────
        jwt_secret = get_jwt_secret()
        jti        = str(uuid.uuid4())
        roles      = db_user.get('roles', [])

        access_payload = {
            'username':      db_user.get('user_email', ''),
            'user_key':      user_key,
            'customer_id':   customer_id,
            'is_super_user': db_user.get('is_super_user', False),
            'roles':         roles,
            'exp':           now + timedelta(minutes=ACCESS_TOKEN_MINUTES),
            'iat':           now,
            'jti':           jti
        }

        if jwt is None:
            access_token = 'jwt-not-available'
        else:
            access_token = jwt.encode(access_payload, jwt_secret, algorithm='HS256')

        user_data = {
            'username':      db_user.get('user_email', ''),
            'user_key':      user_key,
            'user_name':     db_user.get('user_name', ''),
            'customer_id':   customer_id,
            'is_super_user': db_user.get('is_super_user', False),
            'roles':         roles,
            'status':        db_user.get('status', 'active')
        }

        cookie = build_refresh_cookie(new_token_id)
        logger.info(f"RT12 Silent refresh complete for user_key: {user_key}")

        return refresh_response(200, True,
            data={
                'access_token': access_token,
                'user':         user_data,
                'expires_in':   ACCESS_TOKEN_MINUTES * 60
            },
            cookie=cookie
        )

    except Exception as e:
        logger.error(f"Unexpected error in refresh_token: {str(e)}\n{traceback.format_exc()}")
        return refresh_response(500, False, error="Session refresh failed")


def _revoke_all_user_sessions(user_key):
    """
    Revoke all active refresh tokens for a user.
    Called on token reuse detection (theft signal).
    Uses user_key-index GSI.
    """
    if not user_key:
        return
    try:
        result = REFRESH_TOKENS_TABLE.query(
            IndexName='user_key-index',
            KeyConditionExpression=boto3.dynamodb.conditions.Key('user_key').eq(user_key)
        )
        for item in result.get('Items', []):
            if not item.get('revoked'):
                REFRESH_TOKENS_TABLE.update_item(
                    Key={'token_id': item['token_id']},
                    UpdateExpression='SET revoked = :t',
                    ExpressionAttributeValues={':t': True}
                )
        logger.warning(f"SECURITY: All sessions revoked for user_key={user_key} due to token reuse")
    except Exception as e:
        logger.error(f"Error revoking all sessions for {user_key}: {str(e)}")
