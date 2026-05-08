# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Webhook Receiver
Receives webhook notifications from payment processors
Supports AWS API Gateway V2 with header-based authentication
"""
import json
import boto3
import traceback
import hmac
import hashlib
from datetime import datetime
from decimal import Decimal
from utils.track_api_call import tracked
from utils.lambda_utils import extract_user_context,decimal_default,create_response


dynamodb = boto3.resource('dynamodb')
sqs = boto3.client('sqs')

WEBHOOKS_TABLE = dynamodb.Table('WebhookEvent')
WEBHOOK_QUEUE_URL = 'https://sqs.us-east-1.amazonaws.com/123456789/webhook-processing-queue'



@tracked
def verify_signature(payload, signature, secret, algorithm='sha256'):
    """Verify webhook signature"""
    if algorithm == 'sha256':
        expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    elif algorithm == 'md5':
        expected = hmac.new(secret.encode(), payload.encode(), hashlib.md5).hexdigest()
    else:
        return False
    return hmac.compare_digest(expected, signature)

def lambda_handler(event, context):
    """
    Receive webhook from payment processor
    POST /webhooks/{processor_type}
    
    Headers:
    - X-Processor-Type: merchantone|paysafe|paymentnerds
    - X-Signature: Webhook signature
    - X-Webhook-ID: Unique webhook ID (optional)
    """
    print(f"Event: {json.dumps(event, default=decimal_default)}")
    print(f"Context: {context}")
    
    try:
        http_method = event.get('requestContext', {}).get('http', {}).get('method')
        
        if http_method == 'OPTIONS':
            return create_response(200, True)
        
        user_context = extract_user_context(event)
        print(f"User context: {json.dumps(user_context)}")
        
        headers = event.get('headers', {})
        processor_type = headers.get('X-Processor-Type', headers.get('x-processor-type', '')).lower()
        signature = headers.get('X-Signature', headers.get('x-signature', ''))
        webhook_id = headers.get('X-Webhook-ID', headers.get('x-webhook-id'))
        
        if not processor_type:
            return create_response(400, False, error="X-Processor-Type header is required")
        
        # Parse body
        raw_body = event.get('body', '')
        if isinstance(raw_body, str):
            body = json.loads(raw_body) if raw_body else {}
        else:
            body = raw_body
            raw_body = json.dumps(body)
        
        # Generate webhook ID if not provided
        if not webhook_id:
            webhook_id = f"wh_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{processor_type}"
        
        timestamp = datetime.utcnow().isoformat()
        
        # Verify signature (if available)
        signature_verified = None
        # Note: In production, retrieve webhook_secret from Secrets Manager or environment
        # webhook_secret = get_webhook_secret(processor_type)
        
        if signature:
            print(f"Signature verification for {processor_type}: skipped (no secret configured)")
            signature_verified = None
        
        # Store webhook in DynamoDB
        webhook_record = {
            'webhook_key': webhook_id,
            'customer_id': user_context['customer_id'] or 'unknown',
            'processor_type': processor_type,
            'created_at': timestamp,
            'signature_verified': signature_verified,
            'status': 'pending',
            'payload': body,
            'headers': {
                'signature': signature,
                'content_type': headers.get('Content-Type', headers.get('content-type')),
                'user_agent': headers.get('User-Agent', headers.get('user-agent'))
            },
            'retry_count': 0
        }
        
        WEBHOOKS_TABLE.put_item(Item=webhook_record)
        print(f"Webhook stored: {webhook_id}")
        
        # Queue webhook for processing
        if WEBHOOK_QUEUE_URL:
            message = {
                'webhook_id': webhook_id,
                'processor_type': processor_type,
                'timestamp': timestamp
            }
            
            sqs.send_message(
                QueueUrl=WEBHOOK_QUEUE_URL,
                MessageBody=json.dumps(message),
                MessageAttributes={
                    'processor_type': {'StringValue': processor_type, 'DataType': 'String'},
                    'webhook_id': {'StringValue': webhook_id, 'DataType': 'String'}
                }
            )
            print(f"Webhook queued for processing: {webhook_id}")
        
        response_data = {
            'webhook_id': webhook_id,
            'status': 'received',
            'message': 'Webhook received and queued for processing'
        }
        
        if signature_verified is not None:
            response_data['signature_verified'] = signature_verified
        
        return create_response(200, True, response_data)
        
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {str(e)}")
        print(traceback.format_exc())
        return create_response(400, False, error="Invalid JSON in request body")
    except Exception as e:
        print(f"Error receiving webhook: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to receive webhook: {str(e)}")
