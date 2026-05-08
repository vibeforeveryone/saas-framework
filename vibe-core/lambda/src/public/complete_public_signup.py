# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Complete Public Signup
Atomic creation of customer + user + default role assignments + license history.

Write order (rollback is reverse):
  1. Customer             (Customers table)
  2. Admin user           (User table)
  3. Default roles        (UserRole table — non-fatal, NOT rolled back)
  4. License history row  (CustomerLicenseHistory table)
  5. Welcome email        (SES — non-fatal)
"""
import json
import boto3
import os
import logging
from datetime import datetime
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from utils.cors_utils   import create_response
from utils.guid_utils   import generate_guid
from utils.auth_utils   import hash_password
from utils.role_utils   import assign_all_default_roles
from boto3.dynamodb.conditions import Key

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

dynamodb = boto3.resource('dynamodb')
ses      = boto3.client('ses', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

customers_table = dynamodb.Table(
    os.environ.get('CUSTOMERS_TABLE', 'Customers'))
user_table = dynamodb.Table(
    os.environ.get('USER_TABLE', 'User'))
customer_license_history_table = dynamodb.Table(
    os.environ.get('CUSTOMER_LICENSE_HISTORY_TABLE', 'CustomerLicenseHistory'))

FROM_EMAIL = os.environ.get('FROM_EMAIL', 'noreply@yourdomain.com')


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_signup_data(admin_user, customer_data, payment_token):
    """Validate all required signup data."""
    if not admin_user.get('first_name'):             return "First name is required"
    if not admin_user.get('last_name'):              return "Last name is required"
    if not admin_user.get('email'):                  return "Email is required"
    if not admin_user.get('password'):               return "Password is required"
    if len(admin_user.get('password', '')) < 8:      return "Password must be at least 8 characters"
    if not customer_data.get('customer_name'):       return "Company name is required"
    if not customer_data.get('address_line1'):       return "Address is required"
    if not customer_data.get('city'):                return "City is required"
    if not customer_data.get('state'):               return "State/Province is required"
    if not customer_data.get('postal_code'):         return "Postal code is required"
    if not customer_data.get('country'):             return "Country is required"
    if not customer_data.get('phone'):               return "Company phone is required"
    if not payment_token:                            return "Payment verification is required"
    return None


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------

def rollback_resources(created_resources):
    """
    Rollback created resources on fatal failure.
    Delete order is reverse of creation:
      license_history_row -> user -> customer

    Role assignments are NOT rolled back — they are non-fatal and
    the user record they reference will be deleted by the user rollback.
    """
    logger.warning(f"Rolling back created resources: {json.dumps(created_resources)}")

    try:
        # 1. Delete license history row
        if created_resources.get('license_history_key'):
            try:
                customer_license_history_table.delete_item(
                    Key={'history_key': created_resources['license_history_key']}
                )
                logger.info(
                    f"Rolled back license history: "
                    f"{created_resources['license_history_key']}"
                )
            except Exception as e:
                logger.error(f"Error rolling back license history: {str(e)}")

        # 2. Delete user
        if created_resources.get('user_key'):
            try:
                user_table.delete_item(Key={'user_key': created_resources['user_key']})
                logger.info(f"Rolled back user: {created_resources['user_key']}")
            except Exception as e:
                logger.error(f"Error rolling back user: {str(e)}")

        # 3. Mark customer inactive (preserve record for support investigation)
        if created_resources.get('customer_id'):
            try:
                customers_table.update_item(
                    Key={'customer_id': created_resources['customer_id']},
                    UpdateExpression='SET #status = :status, error_message = :error',
                    ExpressionAttributeNames={'#status': 'status'},
                    ExpressionAttributeValues={
                        ':status': 'inactive',
                        ':error':  'Signup incomplete - please contact support'
                    }
                )
                logger.warning(
                    f"Marked customer inactive: {created_resources['customer_id']}"
                )
            except Exception as e:
                logger.error(f"Error marking customer inactive: {str(e)}")

    except Exception as e:
        logger.error(f"Error during rollback: {str(e)}")


# ---------------------------------------------------------------------------
# Welcome email
# ---------------------------------------------------------------------------

def send_welcome_email(email, first_name, customer_name, customer_id,
                       subscription_count, assigned_roles):
    """Send welcome email via SES. Non-fatal."""
    try:
        roles_html = (
            ''.join(f'<li>{r}</li>' for r in assigned_roles)
            if assigned_roles
            else '<li>None assigned — contact your administrator</li>'
        )

        email_body_html = f"""<html><body style="font-family:Arial,sans-serif">
        <div style="max-width:600px;margin:0 auto;padding:20px">
            <div style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);
                        color:white;padding:30px;text-align:center;
                        border-radius:10px 10px 0 0">
                <h1>Welcome to Our Platform!</h1>
            </div>
            <div style="background:#f8f9fa;padding:30px;border-radius:0 0 10px 10px">
                <p>Hello {first_name},</p>
                <p>Congratulations! Your registration is complete.</p>
                <div style="background:white;border-left:4px solid #667eea;
                            padding:15px;margin:20px 0">
                    <p><strong>Company:</strong> {customer_name}</p>
                    <p><strong>Customer ID:</strong> {customer_id}</p>
                    <p><strong>Login Email:</strong> {email}</p>
                    <p><strong>Active Subscriptions:</strong> {subscription_count}</p>
                    <p><strong>Your Roles:</strong></p>
                    <ul>{roles_html}</ul>
                </div>
                <p><strong>Next Steps:</strong></p>
                <ul>
                    <li>Log in to your dashboard</li>
                    <li>Complete your company profile</li>
                    <li>Invite team members</li>
                    <li>Explore your subscribed applications</li>
                </ul>
            </div>
        </div></body></html>"""

        ses.send_email(
            Source=FROM_EMAIL,
            Destination={'ToAddresses': [email]},
            Message={
                'Subject': {
                    'Data':    f'Welcome to Our Platform, {first_name}!',
                    'Charset': 'UTF-8'
                },
                'Body': {
                    'Text': {
                        'Data': (
                            f'Welcome {first_name}! Your registration for '
                            f'{customer_name} is complete. '
                            f'Customer ID: {customer_id}'
                        ),
                        'Charset': 'UTF-8'
                    },
                    'Html': {'Data': email_body_html, 'Charset': 'UTF-8'}
                }
            }
        )
        logger.info(f"Welcome email sent to {email}")
    except Exception as e:
        logger.error(f"Error sending welcome email (non-fatal): {str(e)}")


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------

def lambda_handler(event, context):
    """
    Complete public signup.
    POST /public/complete-signup

    Body:
      admin_user:      { first_name, last_name, email, phone, password }
      customer:        { customer_name, address_line1, city, state,
                         postal_code, country, phone, address_line2? }
      payment_token:   "tok_..."
      payment_details: { last4, card_brand, expiry_month, expiry_year }
      license_key:     "uuid"
    """
    created_resources = {
        'customer_id':         None,
        'user_key':            None,
        'license_history_key': None,
        # role assignments intentionally absent — non-fatal, not rolled back
    }

    try:
        if event.get('httpMethod') == 'OPTIONS':
            from utils.cors_utils import get_cors_headers
            return {'statusCode': 200, 'headers': get_cors_headers(), 'body': ''}

        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})

        # Handle double-serialized body from HTTP API V2
        if isinstance(body, str):
            body = json.loads(body)

        logger.info(f"Parsed body: {json.dumps(body)}")

        admin_user    = body.get('admin_user', {})
        customer_data = body.get('customer', {})
        payment_token = body.get('payment_token', '')
        license_key   = body.get('license_key')

        if not license_key:
            return create_response(400, False, error="license_key is required")

        logger.info(f"LAMBDA HANDLER")
        logger.info(f"admin_user: {admin_user}")
        logger.info(f"payment_token: {payment_token}")
        logger.info(f"license_key: {license_key}")
        logger.info(f"customer_data: {customer_data}")

        # ── Validate ──────────────────────────────────────────────────
        validation_error = validate_signup_data(admin_user, customer_data, payment_token)
        if validation_error:
            return create_response(400, False, error=validation_error)

        # ── Duplicate email check ─────────────────────────────────────
        admin_email = admin_user.get('email', '').lower().strip()
        logger.info(f"LH1 admin_email {admin_email}")

        try:
            email_check = user_table.query(
                IndexName='user_email-index',
                KeyConditionExpression=Key('user_email').eq(admin_email)
            )
            existing_active = [
                u for u in email_check.get('Items', [])
                if u.get('status', 'active') == 'active'
            ]
            if existing_active:
                logger.warning(f"Duplicate email rejected: {admin_email}")
                return create_response(
                    409, False,
                    error="This email address is already registered. "
                          "Please use a different email."
                )
        except Exception as e:
            logger.error(f"Error checking duplicate email: {str(e)}")
            return create_response(500, False,
                error="Unable to verify email availability")

        # ── Generate IDs ──────────────────────────────────────────────
        customer_id = generate_guid()
        user_key    = generate_guid()
        timestamp   = datetime.utcnow().isoformat()

        logger.info(f"LH20 customer_id {customer_id}")
        logger.info(f"LH21 user_key {user_key}")
        logger.info(f"LH22 timestamp {timestamp}")

        # ── 1. Create Customer ────────────────────────────────────────
        try:
            customer_record = {
                'customer_id':   customer_id,
                'customer_name': customer_data.get('customer_name'),
                'first_name':    admin_user.get('first_name'),
                'last_name':     admin_user.get('last_name'),
                'email':         admin_user.get('email'),
                'phone':         customer_data.get('phone'),
                'address':       customer_data.get('address_line1'),
                'address_line2': customer_data.get('address_line2', ''),
                'city':          customer_data.get('city'),
                'state':         customer_data.get('state'),
                'zip':           customer_data.get('postal_code'),
                'country':       customer_data.get('country'),
                'status':        'active',
                'created_at':    timestamp,
                'modified_at':   timestamp,
                'signup_type':   'public_self_service',
            }
            customers_table.put_item(Item=customer_record)
            created_resources['customer_id'] = customer_id
            logger.info(f"Customer created: {customer_id}")

        except Exception as e:
            logger.error(f"Error creating customer: {str(e)}")
            rollback_resources(created_resources)
            return create_response(500, False,
                error=f"Failed to create customer: {str(e)}")

        # ── 2. Create Admin User ──────────────────────────────────────
        try:
            user_record = {
                'user_key':      user_key,
                'customer_id':   customer_id,
                'user_email':    admin_email,
                'password_hash': hash_password(admin_user.get('password')),
                'status':        'active',
                'is_super_user': False,
                'created_at':    timestamp,
                'modified_at':   timestamp,
                'created_by':    'public_signup',
            }
            user_table.put_item(Item=user_record)
            created_resources['user_key'] = user_key
            logger.info(f"User created: {user_key} ({admin_email})")

        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            rollback_resources(created_resources)
            return create_response(500, False,
                error=f"Failed to create user: {str(e)}")

        # ── 3. Assign default roles (Admin + Invoicing) — non-fatal ──
        logger.info(f"LH30 assigning default roles to user {user_key}")
        assigned_roles = assign_all_default_roles(
            user_key=user_key,
            customer_id=customer_id,
            timestamp=timestamp,
            assigned_by='public_signup',
        )
        logger.info(f"LH31 roles assigned: {assigned_roles}")

        # ── 4. Create License History Row ─────────────────────────────
        logger.info(f"LH40 creating license history row")
        try:
            history_key    = generate_guid()
            history_record = {
                'history_key':         history_key,
                'customer_id':         customer_id,
                'license_key':         license_key,
                'effective_date':      timestamp,
                'end_date':            'active',
                'changed_by_user_key': user_key,
                'changed_by_type':     'public_signup',
                'created_at':          timestamp,
            }
            customer_license_history_table.put_item(Item=history_record)
            created_resources['license_history_key'] = history_key
            logger.info(f"Created license history row: {history_key}")

        except Exception as e:
            logger.error(f"Error creating license history row: {str(e)}")
            rollback_resources(created_resources)
            return create_response(500, False,
                error=f"Failed to assign license: {str(e)}")

        # ── 5. Send welcome email — non-fatal ─────────────────────────
        logger.info(f"LH50 sending welcome email")
        try:
            send_welcome_email(
                email=admin_user.get('email'),
                first_name=admin_user.get('first_name'),
                customer_name=customer_data.get('customer_name'),
                customer_id=customer_id,
                subscription_count=1,
                assigned_roles=assigned_roles,
            )
        except Exception as e:
            logger.warning(f"Failed to send welcome email (non-fatal): {str(e)}")

        # ── Success ───────────────────────────────────────────────────
        logger.info(f"LH60 create_response 201 customer_id {customer_id}")
        logger.info(f"LH60 create_response 201 user_key {user_key}")

        return create_response(201, True, {
            'customer_id':    customer_id,
            'user_key':       user_key,
            'license_key':    license_key,
            'roles_assigned': assigned_roles,
            'message':        'Registration completed successfully!'
        })

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        rollback_resources(created_resources)
        return create_response(400, False, error="Invalid JSON in request body")

    except Exception as e:
        logger.error(f"Error in complete_public_signup: {str(e)}")
        rollback_resources(created_resources)
        return create_response(500, False,
            error=f"Failed to complete signup: {str(e)}")
