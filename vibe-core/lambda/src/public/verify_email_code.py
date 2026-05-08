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

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

dynamodb = boto3.resource('dynamodb')
VERIFICATION_TABLE = os.environ.get('VERIFICATION_TABLE', 'EmailVerificationCodes')

def lambda_handler(event, context):
    """
    Verify the 6-digit code for email verification
    
    Expected body:
    {
        "email": "user@example.com",
        "code": "123456",
        "code_id": "vc_20250202..."
    }
    """
    try:
        if event.get('httpMethod') == 'OPTIONS':
            return create_response(200, True)

        logger.info(f"Verify email code request: {json.dumps(event)}")

        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})

        # Handle double-serialized body from HTTP API V2
        if isinstance(body, str):
            body = json.loads(body)

        logger.info(f"Parsed body: {json.dumps(body)}")

        email = body.get('email', '').strip().lower()
        code = body.get('code', '').strip()
        code_id = body.get('code_id', '').strip()
        
        if not email:
            return create_response(400, False, error="Email address is required")
        if not code:
            return create_response(400, False, error="Verification code is required")
        if not code_id:
            return create_response(400, False, error="Code ID is required")
        
        # Validate code format
        if not code.isdigit() or len(code) != 6:
            return create_response(400, False, error="Invalid verification code format")
        
        # Retrieve verification record
        table = dynamodb.Table(VERIFICATION_TABLE)
        
        try:
            response = table.get_item(Key={'code_id': code_id})
        except Exception as e:
            logger.error(f"Error retrieving verification record: {str(e)}")
            return create_response(500, False, error="Failed to verify code")
        
        if 'Item' not in response:
            return create_response(404, False, error="Verification code not found or expired")
        
        verification_record = response['Item']
        
        # Validate email matches
        if verification_record.get('email') != email:
            return create_response(400, False, error="Email address does not match")
        
        # Check if already verified
        if verification_record.get('verified'):
            return create_response(200, True, {'verified': True, 'message': 'Email already verified'})
        
        # Check expiration
        expires_at = verification_record.get('expires_at')
        if expires_at:
            expires_datetime = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            if datetime.utcnow() > expires_datetime:
                return create_response(400, False, error="Verification code has expired")
        
        # Check max attempts
        attempts = int(verification_record.get('attempts', 0))
        max_attempts = int(verification_record.get('max_attempts', 3))
        
        if attempts >= max_attempts:
            return create_response(400, False, error="Maximum verification attempts exceeded")
        
        # Validate the code
        stored_code = verification_record.get('code')
        
        if code != stored_code:
            new_attempts = attempts + 1
            remaining_attempts = max_attempts - new_attempts
            
            try:
                table.update_item(
                    Key={'code_id': code_id},
                    UpdateExpression='SET attempts = :attempts',
                    ExpressionAttributeValues={':attempts': new_attempts}
                )
            except Exception as e:
                logger.error(f"Error updating attempts: {str(e)}")
            
            if remaining_attempts > 0:
                return create_response(400, False, error=f"Invalid verification code. {remaining_attempts} attempt(s) remaining.")
            else:
                return create_response(400, False, error="Invalid verification code. Maximum attempts exceeded.")
        
        # Code is valid - mark as verified
        try:
            table.update_item(
                Key={'code_id': code_id},
                UpdateExpression='SET verified = :verified, verified_at = :verified_at',
                ExpressionAttributeValues={
                    ':verified': True,
                    ':verified_at': datetime.utcnow().isoformat()
                }
            )
        except Exception as e:
            logger.error(f"Error marking as verified: {str(e)}")
            return create_response(500, False, error="Failed to complete verification")
        
        logger.info(f"Email verified successfully: {email}")
        
        return create_response(200, True, {'verified': True, 'message': 'Email verified successfully!'})
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return create_response(400, False, error="Invalid JSON in request body")
    except Exception as e:
        logger.error(f"Error in verify_email_code: {str(e)}")
        return create_response(500, False, error=f"Failed to verify email code: {str(e)}")
