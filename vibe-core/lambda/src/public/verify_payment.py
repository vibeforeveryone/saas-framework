# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
import json
import boto3
import os
import secrets
import logging
from datetime import datetime
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.cors_utils import create_response

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

dynamodb = boto3.resource('dynamodb')
PROCESSOR_CONFIG_TABLE = os.environ.get('PROCESSOR_CONFIG_TABLE', 'ProcessorConfigs')

def validate_card_number(card_number):
    """Validate card number using Luhn algorithm"""
    if not card_number.isdigit():
        return False
    if len(card_number) < 13 or len(card_number) > 19:
        return False
    
    def digits_of(n):
        return [int(d) for d in str(n)]
    
    digits = digits_of(card_number)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    checksum = sum(odd_digits)
    for d in even_digits:
        checksum += sum(digits_of(d * 2))
    return checksum % 10 == 0

def validate_expiry(month, year):
    """Validate card expiry date"""
    try:
        month = int(month)
        year = int(year)
        if month < 1 or month > 12:
            return False
        if year < 100:
            year += 2000
        current_year = datetime.utcnow().year
        current_month = datetime.utcnow().month
        if year < current_year:
            return False
        if year == current_year and month < current_month:
            return False
        return True
    except (ValueError, TypeError):
        return False

def detect_card_type(card_number):
    """Detect card brand from card number"""
    if card_number.startswith('4'):
        return 'Visa'
    elif card_number.startswith('5'):
        return 'Mastercard'
    elif card_number.startswith('3'):
        if card_number.startswith('34') or card_number.startswith('37'):
            return 'American Express'
        else:
            return 'Diners Club'
    elif card_number.startswith('6'):
        return 'Discover'
    else:
        return 'Unknown'

def lambda_handler(event, context):
    """
    Verify payment method and return a token for future billing
    
    Expected body:
    {
        "card_number": "4111111111111111",
        "expiry_month": "12",
        "expiry_year": "25",
        "cvv": "123",
        "cardholder_name": "John Doe",
        "billing_address": {...}
    }
    """
    try:
        if event.get('httpMethod') == 'OPTIONS':
            return create_response(200, True)

        logger.info(f"Verify payment request: {json.dumps(event)}")

        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})

        # Handle double-serialized body from HTTP API V2
        if isinstance(body, str):
            body = json.loads(body)

        logger.info(f"Parsed body: {json.dumps(body)}")

        # Extract payment details
        card_number = body.get('card_number', '').replace(' ', '').replace('-', '')
        expiry_month = body.get('expiry_month', '').strip()
        expiry_year = body.get('expiry_year', '').strip()
        cvv = body.get('cvv', '').strip()
        cardholder_name = body.get('cardholder_name', '').strip()
        billing_address = body.get('billing_address', {})
        
        # Validate required fields
        if not card_number:
            return create_response(400, False, error="Card number is required")
        if not expiry_month or not expiry_year:
            return create_response(400, False, error="Card expiration date is required")
        if not cvv:
            return create_response(400, False, error="CVV is required")
        if not cardholder_name:
            return create_response(400, False, error="Cardholder name is required")
        
        # Validate card number
        if not validate_card_number(card_number):
            return create_response(400, False, error="Invalid card number")
        
        # Validate expiry date
        if not validate_expiry(expiry_month, expiry_year):
            return create_response(400, False, error="Card is expired or invalid expiry date")
        
        # Validate CVV
        if not cvv.isdigit() or len(cvv) < 3 or len(cvv) > 4:
            return create_response(400, False, error="Invalid CVV")
        
        # Generate token
        payment_token = f"tok_{secrets.token_hex(16)}"
        last4 = card_number[-4:]
        card_type = detect_card_type(card_number)
        
        logger.info(f"Payment verified for card ending in {last4}")
        
        return create_response(200, True, {
            'token': payment_token,
            'last4': last4,
            'card_type': card_type.lower(),
            'card_brand': card_type,
            'expiry_month': expiry_month,
            'expiry_year': expiry_year,
            'cardholder_name': cardholder_name
        })
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return create_response(400, False, error="Invalid JSON in request body")
    except Exception as e:
        logger.error(f"Error in verify_payment: {str(e)}")
        return create_response(500, False, error=f"Failed to verify payment: {str(e)}")
