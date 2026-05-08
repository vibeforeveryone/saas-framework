# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
import json
import boto3
import os
import secrets
import logging
from datetime import datetime, timedelta
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.cors_utils import create_response

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

dynamodb = boto3.resource('dynamodb')
ses = boto3.client('ses', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

VERIFICATION_TABLE = os.environ.get('VERIFICATION_TABLE', 'EmailVerificationCodes')
FROM_EMAIL = os.environ.get('FROM_EMAIL', 'noreply@yourdomain.com')
CODE_EXPIRY_MINUTES = 15
MAX_ATTEMPTS_PER_HOUR = 3

def lambda_handler(event, context):
    """
    Send a 6-digit verification code to the provided email address
    
    HTTP API V2 Event Structure
    Expected body:
    {
        "email": "user@example.com"
    }
    """
    try:
        if event.get('httpMethod') == 'OPTIONS':
            return create_response(200, True)

        logger.info(f"Send verification code request: {json.dumps(event)}")

        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})

        # Handle double-serialized body from HTTP API V2
        if isinstance(body, str):
            body = json.loads(body)

        logger.info(f"Parsed body: {json.dumps(body)}")

        email = body.get('email', '').strip().lower()
        
        if not email:
            return create_response(400, False, error="Email address is required")
        
        # Validate email format
        if '@' not in email or '.' not in email.split('@')[1]:
            return create_response(400, False, error="Invalid email address format")
        
        # Rate limiting: Check recent attempts
        table = dynamodb.Table(VERIFICATION_TABLE)
        one_hour_ago = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        
        try:
            response = table.query(
                IndexName='email-timestamp-index',
                KeyConditionExpression='email = :email AND #ts > :one_hour_ago',
                ExpressionAttributeNames={'#ts': 'timestamp'},
                ExpressionAttributeValues={
                    ':email': email,
                    ':one_hour_ago': one_hour_ago
                }
            )
            
            recent_attempts = response.get('Items', [])
            if len(recent_attempts) >= MAX_ATTEMPTS_PER_HOUR:
                return create_response(429, False, error="Too many verification attempts. Please try again later.")
        except Exception as e:
            logger.warning(f"Error checking rate limit: {str(e)}")
        verification_code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
        code_id = f"vc_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}"
        expires_at = datetime.utcnow() + timedelta(minutes=CODE_EXPIRY_MINUTES)
        expires_at_iso = expires_at.isoformat()
        expires_at_unix = int(expires_at.timestamp())
        
        # Store verification code
        verification_record = {
            'code_id': code_id,
            'email': email,
            'code': verification_code,
            'timestamp': datetime.utcnow().isoformat(),
            'expires_at': expires_at_iso,
            'ttl': expires_at_unix + 3600,
            'verified': False,
            'attempts': 0,
            'max_attempts': 3
        }
        
        table.put_item(Item=verification_record)
        
        # Send email via SES
        try:
            email_body_html = f"""<html><body style="font-family:Arial,sans-serif">
            <div style="max-width:600px;margin:0 auto;padding:20px">
                <div style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white;padding:30px;text-align:center;border-radius:10px 10px 0 0">
                    <h1>🔐 Email Verification</h1>
                </div>
                <div style="background:#f8f9fa;padding:30px;border-radius:0 0 10px 10px">
                    <p>Thank you for signing up! Please enter this verification code:</p>
                    <div style="background:white;border:2px solid #667eea;border-radius:8px;padding:20px;text-align:center;margin:20px 0;font-size:32px;font-weight:bold;letter-spacing:8px;color:#667eea">
                        {verification_code}
                    </div>
                    <p><strong>Expires in {CODE_EXPIRY_MINUTES} minutes.</strong></p>
                    <div style="background:#fff3cd;border-left:4px solid #ffc107;padding:10px;margin:20px 0">
                        ⚠️ If you did not request this code, please ignore this email.
                    </div>
                </div>
            </div></body></html>"""
            
            ses.send_email(
                Source=FROM_EMAIL,
                Destination={'ToAddresses': [email]},
                Message={
                    'Subject': {'Data': 'Your Verification Code', 'Charset': 'UTF-8'},
                    'Body': {
                        'Text': {'Data': f'Your verification code is: {verification_code}\n\nExpires in {CODE_EXPIRY_MINUTES} minutes.', 'Charset': 'UTF-8'},
                        'Html': {'Data': email_body_html, 'Charset': 'UTF-8'}
                    }
                }
            )
            logger.info(f"Verification code sent to {email}")
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return create_response(500, False, error="Failed to send verification email")
        
        return create_response(200, True, {
            'code_id': code_id,
            'expires_at': expires_at_iso,
            'message': f'Verification code sent to {email}'
        })
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return create_response(400, False, error="Invalid JSON in request body")
    except Exception as e:
        logger.error(f"Error in send_verification_code: {str(e)}")
        return create_response(500, False, error=f"Failed to send verification code: {str(e)}")
