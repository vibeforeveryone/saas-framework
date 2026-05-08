# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Notification Service
Send notifications for transactions, disputes, and webhooks
Supports AWS API Gateway V2 with header-based authentication
"""
import json
import boto3
import traceback
from datetime import datetime
from decimal import Decimal
from utils.track_api_call import tracked
from utils.lambda_utils import extract_user_context,decimal_default,create_response


ses = boto3.client('ses')
sns = boto3.client('sns')

FROM_EMAIL = 'noreply@example.com'
SNS_TOPIC_ARN = 'arn:aws:sns:us-east-1:123456789:notifications'


@tracked
def send_email_notification(to_email, subject, body_html, body_text=None):
    """Send email via SES"""
    try:
        if not body_text:
            body_text = body_html.replace('<br>', '\n').replace('<p>', '').replace('</p>', '\n')
        
        response = ses.send_email(
            Source=FROM_EMAIL,
            Destination={'ToAddresses': [to_email]},
            Message={
                'Subject': {'Data': subject},
                'Body': {
                    'Text': {'Data': body_text},
                    'Html': {'Data': body_html}
                }
            }
        )
        
        print(f"Email sent to {to_email}: {response['MessageId']}")
        return True, response['MessageId']
        
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        print(traceback.format_exc())
        return False, str(e)

def send_sms_notification(phone_number, message):
    """Send SMS via SNS"""
    try:
        response = sns.publish(
            PhoneNumber=phone_number,
            Message=message
        )
        
        print(f"SMS sent to {phone_number}: {response['MessageId']}")
        return True, response['MessageId']
        
    except Exception as e:
        print(f"Error sending SMS: {str(e)}")
        print(traceback.format_exc())
        return False, str(e)

def format_payment_notification(transaction_data):
    """Format payment notification"""
    status = transaction_data['status']
    amount = transaction_data['amount']
    currency = transaction_data['currency']
    
    if status == 'completed':
        subject = f"Payment Successful - {currency} {amount}"
        body = f"""
        <h2>Payment Successful</h2>
        <p>Your payment has been processed successfully.</p>
        <p><strong>Transaction ID:</strong> {transaction_data['transaction_id']}</p>
        <p><strong>Amount:</strong> {currency} {amount}</p>
        <p><strong>Date:</strong> {transaction_data['created_at']}</p>
        <p>Thank you for your payment!</p>
        """
    else:
        subject = f"Payment Failed - {currency} {amount}"
        body = f"""
        <h2>Payment Failed</h2>
        <p>Unfortunately, your payment could not be processed.</p>
        <p><strong>Transaction ID:</strong> {transaction_data['transaction_id']}</p>
        <p><strong>Amount:</strong> {currency} {amount}</p>
        <p>Please try again or contact support.</p>
        """
    
    return subject, body

def lambda_handler(event, context):
    """
    Send notification
    POST /notifications
    
    Expected payload:
    {
        "notification_type": "payment|refund|dispute",
        "channel": "email|sms",
        "recipient": "email@example.com or +1234567890",
        "data": {}
    }
    """
    print(f"Event: {json.dumps(event, default=decimal_default)}")
    print(f"Context: {context}")
    
    try:
        http_method = event.get('requestContext', {}).get('http', {}).get('method')
        
        if http_method == 'OPTIONS':
            return create_response(200, True)
        
        user_context = extract_user_context(event)
        print(f"User context: {json.dumps(user_context)}")
        
        # Parse body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        notification_type = body.get('notification_type')
        channel = body.get('channel', 'email')
        recipient = body.get('recipient')
        data = body.get('data', {})
        
        if not notification_type or not recipient:
            return create_response(400, False, error="notification_type and recipient are required")
        
        # Format notification
        subject = None
        message = None
        
        if notification_type == 'payment':
            subject, message = format_payment_notification(data)
        else:
            subject = body.get('subject', 'Notification')
            message = body.get('message', '')
        
        # Send notification
        success = False
        message_id = None
        
        if channel == 'email':
            success, message_id = send_email_notification(recipient, subject, message)
        elif channel == 'sms':
            success, message_id = send_sms_notification(recipient, message)
        else:
            return create_response(400, False, error=f"Unsupported channel: {channel}")
        
        if success:
            return create_response(200, True, {
                'notification_type': notification_type,
                'channel': channel,
                'recipient': recipient,
                'message_id': message_id,
                'sent_by': user_context['user_id']
            })
        else:
            return create_response(500, False, error=f"Failed to send notification: {message_id}")
        
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {str(e)}")
        print(traceback.format_exc())
        return create_response(400, False, error="Invalid JSON in request body")
    except Exception as e:
        print(f"Error sending notification: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to send notification: {str(e)}")
