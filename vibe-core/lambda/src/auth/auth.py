# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Authentication
Authenticates users, generates short-lived JWT access tokens (15 min),
and issues httpOnly refresh token cookies (24 hr).

POST /auth
"""
import json
import boto3
import os
import traceback
import hashlib
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from boto3.dynamodb.conditions import Key
import logging

from utils.lambda_utils import extract_user_context, decimal_default, create_response

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

try:
    import jwt
except ImportError:
    logger.warning("WARNING: jwt module not available")
    jwt = None

# ── AWS clients ──────────────────────────────────────────────────────────────
dynamodb        = boto3.resource('dynamodb')
secrets_client  = boto3.client('secretsmanager')

USER_TABLE          = dynamodb.Table('User')
REFRESH_TOKENS_TABLE = dynamodb.Table(os.environ.get('REFRESH_TOKENS_TABLE', 'RefreshTokens'))

# ── Config ───────────────────────────────────────────────────────────────────
ALLOWED_ORIGIN          = os.environ.get('ALLOWED_ORIGIN', 'http://localhost:3000')
ENVIRONMENT             = os.environ.get('ENVIRONMENT', 'dev')
REFRESH_TOKEN_TTL_HOURS = int(os.environ.get('REFRESH_TOKEN_TTL_HOURS', '24'))
ACCESS_TOKEN_MINUTES    = 15

# ── JWT secret — fetched from Secrets Manager once per cold start ─────────────
_jwt_secret = None


#this get_jwt_secret() in logout and refresh_token is different than Auth, and needs to be reviewed as it is brought back into play
def get_jwt_secret():
    """Fetch JWT secret from Secrets Manager. Cached after first call."""
    global _jwt_secret
    if _jwt_secret is None:
        try:
            logger.info("Fetching JWT secret from Secrets Manager")
            response = secrets_client.get_secret_value(SecretId='vfeVer1/jwt-access-secret')
            logger.info(f"Fetching JWT response =  {response}")
            _jwt_secret = json.loads(response['SecretString'])['secret']
            logger.info(f"JWT secret loaded successfully _jwt_secret{_jwt_secret}")
        except Exception as e:
            logger.error(f"Failed to load JWT secret from Secrets Manager: {str(e)}")
            raise RuntimeError("Unable to load JWT secret") from e
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


# ── Cookie builder ───────────────────────────────────────────────────────────
def build_refresh_cookie(token_value, clear=False):
    """
    Build the Set-Cookie string for the refresh token.
    - dev:  SameSite=Lax  (no Secure — allows HTTP localhost)
    - prod: SameSite=Strict; Secure
    clear=True sets Max-Age=0 to delete the cookie.
    """
    if clear:
        return (
            f"refresh_token=; HttpOnly; Path=/auth; Max-Age=0; SameSite=Strict"
        )

    max_age = REFRESH_TOKEN_TTL_HOURS * 3600

    if ENVIRONMENT == 'prod':
        same_site = "Strict"
        secure    = "; Secure"
    else:
        same_site = "Lax"
        secure    = ""

    return (
        f"refresh_token={token_value}; HttpOnly; Path=/auth;"
        f" Max-Age={max_age}; SameSite={same_site}{secure}"
    )


def auth_response(status_code, success, data=None, error=None, cookie=None):
    """
    Build an API Gateway HTTP API v2 response that includes a Set-Cookie header.
    The `cookies` array in the response is the correct mechanism for HTTP API v2.
    """
    body = {
        'success': success,
        'data':    data,
        'error':   error,
        'timestamp': datetime.utcnow().isoformat()
    }
    response = {
        'statusCode': status_code,
        'headers': {
            'Content-Type':                     'application/json',
            'Access-Control-Allow-Origin':       ALLOWED_ORIGIN,
            'Access-Control-Allow-Credentials':  'true',
            'Access-Control-Allow-Headers':      (
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


# ── Helpers ───────────────────────────────────────────────────────────────────
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def store_refresh_token(token_id, user_key, customer_id, event):
    """Write a new refresh token record to DynamoDB."""
    now        = datetime.utcnow()
    expires_at = now + timedelta(hours=REFRESH_TOKEN_TTL_HOURS)

    headers    = event.get('headers', {})
    user_agent = headers.get('user-agent') or headers.get('User-Agent', '')
    ip_address = (
        event.get('requestContext', {})
             .get('http', {})
             .get('sourceIp', '')
    )

    REFRESH_TOKENS_TABLE.put_item(Item={
        'token_id':    token_id,
        'user_key':    user_key,
        'customer_id': customer_id,
        'created_at':  now.isoformat(),
        'expires_at':  int(expires_at.timestamp()),   # DynamoDB TTL (epoch seconds)
        'revoked':     False,
        'replaced_by': None,
        'user_agent':  user_agent[:500] if user_agent else '',
        'ip_address':  ip_address
    })
    logger.info(f"RT1 Refresh token stored: {token_id} for user {user_key}")


# ── Handler ───────────────────────────────────────────────────────────────────
def lambda_handler(event, context):
    """
    POST /auth
    Body: { "username": "...", "password": "..." }
    Returns: { access_token, user } + httpOnly refresh_token cookie
    """
    logger.info(f"Auth request received")

    try:
        http_method = event.get('requestContext', {}).get('http', {}).get('method', '')

        if http_method == 'OPTIONS':
            return auth_response(200, True)

        # ── Parse body ───────────────────────────────────────────────────────
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})

        username = body.get('username', '').strip().lower()
        password = body.get('password', '')

        logger.info(f"A1 Login attempt for: {username}")

        if not username or not password:
            return auth_response(400, False, error="Username and password are required")

        # ── Load JWT secret ───────────────────────────────────────────────────
        try:
            logger.info(f"A1a before get secret: {username}")

            jwt_secret = get_jwt_secret()

            logger.info(f"A1b jwt secret is : {jwt_secret}")
        except RuntimeError as e:
            logger.error(str(e))
            return auth_response(500, False, error="Authentication service unavailable")

        # ── Look up user ──────────────────────────────────────────────────────
        try:
            logger.info(f"A11 before lookup user ")
            result = USER_TABLE.query(
                IndexName='user_email-index',
                KeyConditionExpression=Key('user_email').eq(username)
            )
            users = result.get('Items', [])

            logger.info(f"A11 after lookup user {users} ")
        except Exception as e:
            logger.error(f"A2 DynamoDB query error: {str(e)}")
            return auth_response(500, False, error="Authentication service error")

        if not users:
            logger.warning(f"A3 User not found: {username}")
            return auth_response(401, False, error="Invalid credentials")

        db_user       = users[0]
        password_hash = hash_password(password)

        if db_user.get('password_hash') != password_hash:
            logger.warning(f"A4 Password mismatch for: {username}")
            return auth_response(401, False, error="Invalid credentials")

        if db_user.get('status', 'active') != 'active':
            logger.warning(f"A5 Inactive account: {username}")
            return auth_response(403, False, error="Account is not active")

        user_key    = db_user.get('user_key', '')
        customer_id = db_user.get('customer_id', '')
        roles       = db_user.get('roles', [])

        logger.info(f"A6 Credentials valid for user_key: {user_key}")

        # ── Build access token (15 min) ───────────────────────────────────────
        jti = str(uuid.uuid4())
        now = datetime.utcnow()

        access_payload = {
            'username':      username,
            'user_key':      user_key,
            'customer_id':   customer_id,
            'is_super_user': db_user.get('is_super_user', False),
            'roles':         roles,
            'exp':           now + timedelta(minutes=ACCESS_TOKEN_MINUTES),
            'iat':           now,
            'jti':           jti
        }

        if jwt is None:
            logger.warning("A7 JWT module unavailable — returning token-less response")
            access_token = 'jwt-not-available'
        else:
            access_token = jwt.encode(access_payload, jwt_secret, algorithm='HS256')
            logger.info(f"A8 Access token generated (jti={jti})")

        # ── Generate & store refresh token ────────────────────────────────────
        refresh_token_id = str(uuid.uuid4())
        try:
            store_refresh_token(refresh_token_id, user_key, customer_id, event)
        except Exception as e:
            logger.error(f"A9 Failed to store refresh token: {str(e)}")
            return auth_response(500, False, error="Authentication service error")

        # ── Build response ────────────────────────────────────────────────────
        user_data = {
            'username':      username,
            'user_key':      user_key,
            'user_name':     db_user.get('user_name', username),
            'customer_id':   customer_id,
            'is_super_user': db_user.get('is_super_user', False),
            'roles':         roles,
            'status':        db_user.get('status', 'active'),
            'login_time':    now.isoformat()
        }

        cookie = build_refresh_cookie(refresh_token_id)

        logger.info(f"A10 Login successful for {username} — refresh token issued")

        return auth_response(200, True,
            data={
                'access_token': access_token,
                'user':         user_data,
                'expires_in':   ACCESS_TOKEN_MINUTES * 60,
                'message':      'Login successful'
            },
            cookie=cookie
        )

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return auth_response(400, False, error="Invalid JSON in request body")
    except Exception as e:
        logger.error(f"Unexpected error in auth: {str(e)}\n{traceback.format_exc()}")
        return auth_response(500, False, error="Authentication failed")
