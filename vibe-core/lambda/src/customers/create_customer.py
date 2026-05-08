# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Create Customer
Creates a new customer and its first admin user.
The admin user is automatically assigned both default system roles
(Admin + Invoicing) via the shared role_utils utility.

Role assignments are non-fatal: if the Role table lookup fails for any
reason the customer and user are still created successfully, and roles
can be assigned manually via UserManager.
"""
import json
import boto3
import os
import logging
from datetime import datetime, timezone
import hashlib
import secrets
import traceback
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from utils.track_api_call    import tracked
from utils.role_utils         import assign_all_default_roles

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb        = boto3.resource('dynamodb')
customers_table = dynamodb.Table('Customers')
users_table     = dynamodb.Table('User')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_cors_headers():
    return {
        'Access-Control-Allow-Origin':  '*',
        'Access-Control-Allow-Headers': (
            'Content-Type,X-Amz-Date,Authorization,'
            'X-Api-Key,X-Amz-Security-Token,X-User-Id'
        ),
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
        'Access-Control-Max-Age':       '600',
    }


def create_response(status_code, success, data=None, error=None):
    body = {'success': success}
    if data  is not None: body['data']  = data
    if error is not None: body['error'] = error
    return {
        'statusCode': status_code,
        'headers':    get_cors_headers(),
        'body':       json.dumps(body),
    }


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def generate_user_key() -> str:
    return f"user_{secrets.token_hex(8)}"


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------

@tracked
def lambda_handler(event, context):
    """
    Create a new customer with admin user.
    POST /customers

    Body:
      customer_id*, company_name*, name*, email*,
      phone, address, city, state, zip, country, status,
      admin_email*, admin_password*, admin_name
    """
    try:
        # OPTIONS preflight
        method = (event.get('requestContext', {}).get('http', {}).get('method')
                  or event.get('httpMethod', ''))
        if method == 'OPTIONS':
            return {'statusCode': 200, 'headers': get_cors_headers(), 'body': ''}

        # Caller identity
        headers = event.get('headers', {})
        user_id = (headers.get('X-User-Id') or headers.get('x-user-id') or
                   headers.get('userId') or 'system')

        logger.info(f"Create customer request — caller: {user_id}")
        logger.info(f"Event: {json.dumps(event)}")

        # Parse body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})

        # ── Validation ────────────────────────────────────────────────
        for field in ('customer_id', 'company_name', 'name', 'email'):
            if not body.get(field):
                return create_response(400, False,
                    error=f"Missing required field: {field}")

        if not body.get('admin_email'):
            return create_response(400, False, error="admin_email is required")

        if not body.get('admin_password'):
            return create_response(400, False, error="admin_password is required")

        if len(body.get('admin_password', '')) < 8:
            return create_response(400, False,
                error="admin_password must be at least 8 characters")

        # Duplicate customer check
        existing = customers_table.get_item(Key={'customer_id': body['customer_id']})
        if 'Item' in existing:
            logger.warning(f"Customer already exists: {body['customer_id']}")
            return create_response(409, False,
                error=f"Customer {body['customer_id']} already exists")

        timestamp   = datetime.now(timezone.utc).isoformat()
        customer_id = str(body['customer_id'])
        admin_email = str(body['admin_email']).lower().strip()

        # make_user_super: accepts True (bool) or "true" (string), defaults False
        raw_super   = body.get('make_user_super', False)
        is_super    = raw_super is True or str(raw_super).lower() == 'true'
        if is_super:
            logger.info(f"make_user_super=true — user will be created as superuser")

        # ── 1. Build and write customer record ────────────────────────
        customer_record = {
            'customer_id':  customer_id,
            'company_name': str(body['company_name']),
            'name':         str(body['name']),
            'email':        str(body['email']),
            'phone':        str(body.get('phone',   '')),
            'address':      str(body.get('address', '')),
            'city':         str(body.get('city',    '')),
            'state':        str(body.get('state',   '')),
            'zip':          str(body.get('zip',     '')),
            'country':      str(body.get('country', '')),
            'status':       body.get('status', 'active'),
            'created_at':   timestamp,
            'updated_at':   timestamp,
            'created_by':   user_id,
            'updated_by':   user_id,
        }
        customers_table.put_item(Item=customer_record)
        logger.info(f"Created customer: {customer_id} ({body['company_name']})")

        # ── 2. Build and write admin user record ──────────────────────
        user_key = generate_user_key()

        logger.info(f"admin_email: {admin_email}")
        admin_password_hash = hash_password(str(body['admin_password']))
        logger.info(f"admin_password_hash: {admin_password_hash}")

        admin_user_record = {
            'user_key':      user_key,
            'customer_id':   customer_id,
            'user_name':     admin_email.split('@')[0],
            'user_email':    admin_email,
            'password_hash': admin_password_hash,
            'status':        'active',
            'is_super_user': is_super,
            'created_at':    timestamp,
            'modified_at':   timestamp,
            'created_by':    user_id,
            'modified_by':   user_id,
        }

        try:
            users_table.put_item(Item=admin_user_record)
            logger.info(f"Created admin user: {user_key} ({admin_email}) is_super_user={is_super}")
        except Exception as e:
            logger.error(f"Error creating admin user: {str(e)}")
            traceback.print_exc()
            return create_response(500, False,
                error=f"Customer created but failed to create admin user: {str(e)}")

        # ── 3. Assign default roles (Admin + Invoicing) — non-fatal ──
        logger.info(f"Assigning default roles to user {user_key}")
        assigned_roles = assign_all_default_roles(
            user_key=user_key,
            customer_id=customer_id,
            timestamp=timestamp,
            assigned_by=user_id,
        )
        logger.info(f"Roles assigned: {assigned_roles}")

        return create_response(201, True, {
            'customer':   customer_record,
            'admin_user': {
                'user_key':       user_key,
                'user_name':      admin_user_record['user_name'],
                'user_email':     admin_email,
                'is_super_user':  is_super,
                'roles_assigned': assigned_roles,
            },
            'message': (
                f"Customer and admin user created successfully. "
                f"Roles assigned: {', '.join(assigned_roles) or 'none (see logs)'}"
            ),
        })

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return create_response(400, False, error="Invalid JSON in request body")

    except Exception as e:
        logger.error(f"Error creating customer: {str(e)}")
        traceback.print_exc()
        return create_response(500, False,
            error=f"Failed to create customer: {str(e)}")
