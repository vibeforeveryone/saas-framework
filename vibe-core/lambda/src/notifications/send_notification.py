# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Lambda function for sending notifications via email, SMS, and push
Supports AWS API Gateway V2 with header-based authentication
"""
import json
import boto3
import traceback
from datetime import datetime
from decimal import Decimal
from utils.track_api_call import tracked
from utils.lambda_utils import extract_user_context,decimal_default,create_response

# AWS Clients
sns = boto3.client('sns')
ses = boto3.client('ses')
dynamodb = boto3.resource('dynamodb')

# Hardcoded table names
PREFERENCES_TABLE = dynamodb.Table('NotificationPreferencesTable')
DIGEST_QUEUE_TABLE = dynamodb.Table('DigestQueueTable')
NOTIFICATION_HISTORY_TABLE = dynamodb.Table('NotificationHistoryTable')



@tracked
def lambda_handler(event, context):
    """
    Send notifications through various channels based on user preferences
    POST /notifications - Send a notification
    """
    
    # Log comprehensive request context
    print(f"Event: {json.dumps(event)}")
    print(f"Context: {context}")
    
    try:
        # Handle OPTIONS preflight request
        if event.get('requestContext', {}).get('http', {}).get('method') == 'OPTIONS':
            return create_response(200, True)
        
        # Extract user context from headers
        user_context = extract_user_context(event)
        print(f"User context: {json.dumps(user_context)}")
        
        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        # Validate required fields
        required_fields = ['type', 'recipients', 'subject', 'body']
        missing_fields = [field for field in required_fields if field not in body]
        
        if missing_fields:
            return create_response(400, False, 
                error=f"Missing required fields: {', '.join(missing_fields)}")
        
        notification_type = body.get('type')
        recipients = body.get('recipients', [])
        customer_id = user_context['provider_id'] or body.get('customer_id')
        subject = body.get('subject')
        message_body = body.get('body')
        data = body.get('data', {})
        priority = body.get('priority', 'normal')
        
        if not customer_id:
            return create_response(400, False, error="Company ID is required")
        
        # Process notification for each recipient
        results = []
        for recipient_id in recipients:
            result = process_notification(
                customer_id=customer_id,
                recipient_id=recipient_id,
                notification_type=notification_type,
                subject=subject,
                body=message_body,
                data=data,
                priority=priority,
                sent_by=user_context['user_id']
            )
            results.append(result)
        
        print(f"Notification processing completed: {len(results)} recipients")
        
        return create_response(200, True, {
            'message': 'Notifications processed successfully',
            'results': results,
            'total_recipients': len(recipients)
        })
        
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {str(e)}")
        print(traceback.format_exc())
        return create_response(400, False, error="Invalid JSON in request body")
    except Exception as e:
        print(f"Error sending notification: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to send notification: {str(e)}")

def process_notification(customer_id, recipient_id, notification_type, subject, body, data, priority, sent_by):
    """Process a notification request for a single recipient"""
    try:
        # Get user preferences
        prefs = get_user_preferences(customer_id, recipient_id)
        
        # Check quiet hours
        if should_skip_quiet_hours(prefs, priority):
            print(f"Skipping notification for {recipient_id} due to quiet hours")
            return {
                'recipient_id': recipient_id,
                'status': 'skipped',
                'reason': 'quiet_hours'
            }
        
        # Check notification frequency
        if should_batch_notification(prefs, priority):
            queue_for_digest(customer_id, recipient_id, {
                'type': notification_type,
                'subject': subject,
                'body': body,
                'data': data,
                'priority': priority
            })
            return {
                'recipient_id': recipient_id,
                'status': 'queued',
                'reason': 'digest_delivery'
            }
        
        # Track delivery status
        delivery_status = {
            'email': 'not_enabled',
            'sms': 'not_enabled',
            'push': 'not_enabled'
        }
        
        # Send through enabled channels
        if prefs.get('emailNotifications', {}).get(notification_type, False):
            email_result = send_email(recipient_id, subject, body, data)
            delivery_status['email'] = 'sent' if email_result else 'failed'
        
        if prefs.get('smsNotifications', {}).get(notification_type, False):
            sms_result = send_sms(recipient_id, subject, body)
            delivery_status['sms'] = 'sent' if sms_result else 'failed'
        
        if prefs.get('pushNotifications', {}).get(notification_type, False):
            push_result = send_push(recipient_id, subject, body, data)
            delivery_status['push'] = 'sent' if push_result else 'failed'
        
        # Log to notification history
        log_notification_history(
            customer_id=customer_id,
            recipient_id=recipient_id,
            notification_type=notification_type,
            subject=subject,
            body=body,
            delivery_status=delivery_status,
            priority=priority,
            sent_by=sent_by
        )
        
        return {
            'recipient_id': recipient_id,
            'status': 'sent',
            'delivery_status': delivery_status
        }
        
    except Exception as e:
        print(f"Error processing notification for {recipient_id}: {str(e)}")
        print(traceback.format_exc())
        return {
            'recipient_id': recipient_id,
            'status': 'error',
            'error': str(e)
        }

def get_user_preferences(customer_id, user_id):
    """Retrieve user notification preferences"""
    try:
        response = PREFERENCES_TABLE.get_item(
            Key={
                'customer_id': customer_id,
                'userId': user_id
            }
        )
        return response.get('Item', get_default_preferences())
    except Exception as e:
        print(f"Error getting preferences: {str(e)}")
        return get_default_preferences()

def get_default_preferences():
    """Return default notification preferences"""
    return {
        'emailNotifications': {
            'appointments': True,
            'tasks': True,
            'payments': True,
            'disputes': True,
            'systemUpdates': True
        },
        'smsNotifications': {
            'appointments': True,
            'tasks': False,
            'payments': True,
            'disputes': True,
            'systemUpdates': False
        },
        'pushNotifications': {
            'appointments': True,
            'tasks': True,
            'payments': True,
            'disputes': True,
            'systemUpdates': True
        },
        'frequency': 'immediate',
        'quietHours': {
            'enabled': False
        }
    }

def should_skip_quiet_hours(prefs, priority):
    """Check if notification should be skipped due to quiet hours"""
    if priority in ['high', 'urgent']:
        return False  # Never skip high priority notifications
    
    quiet_hours = prefs.get('quietHours', {})
    if not quiet_hours.get('enabled', False):
        return False
    
    # Check if current time is in quiet hours
    now = datetime.utcnow()
    current_time = now.strftime('%H:%M')
    
    start_time = quiet_hours.get('start', '22:00')
    end_time = quiet_hours.get('end', '08:00')
    
    # Handle quiet hours that span midnight
    if start_time > end_time:
        return current_time >= start_time or current_time <= end_time
    else:
        return start_time <= current_time <= end_time

def should_batch_notification(prefs, priority):
    """Check if notification should be batched for digest"""
    if priority in ['high', 'urgent']:
        return False  # Never batch high priority notifications
    
    frequency = prefs.get('frequency', 'immediate')
    return frequency in ['daily_digest', 'weekly_digest']

def queue_for_digest(customer_id, user_id, message):
    """Queue notification for digest delivery"""
    try:
        item = {
            'customer_id': customer_id,
            'userId': user_id,
            'timestamp': datetime.utcnow().isoformat(),
            'message': message
        }
        
        DIGEST_QUEUE_TABLE.put_item(Item=item)
        print(f"Queued notification for digest: {user_id}")
    except Exception as e:
        print(f"Error queuing for digest: {str(e)}")

def send_email(user_id, subject, body, data):
    """Send email notification"""
    try:
        # In production, fetch user email from user table
        user_email = data.get('recipientEmail', f"{user_id}@example.com")
        from_email = data.get('fromEmail', 'noreply@yourdomain.com')
        
        response = ses.send_email(
            Source=from_email,
            Destination={
                'ToAddresses': [user_email]
            },
            Message={
                'Subject': {
                    'Data': subject,
                    'Charset': 'UTF-8'
                },
                'Body': {
                    'Html': {
                        'Data': format_email_html(subject, body, data),
                        'Charset': 'UTF-8'
                    },
                    'Text': {
                        'Data': body,
                        'Charset': 'UTF-8'
                    }
                }
            }
        )
        print(f"Email sent to {user_email}: {response['MessageId']}")
        return True
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        print(traceback.format_exc())
        return False

def send_sms(user_id, subject, body):
    """Send SMS notification"""
    try:
        # In production, fetch user phone from user table
        # For now, skip if no phone number configured
        print(f"SMS delivery not configured for user {user_id}")
        return False
    except Exception as e:
        print(f"Error sending SMS: {str(e)}")
        print(traceback.format_exc())
        return False

def send_push(user_id, subject, body, data):
    """Send push notification"""
    try:
        # In production, use SNS with mobile endpoint or Firebase
        print(f"Push notification delivery not configured for user {user_id}")
        return False
    except Exception as e:
        print(f"Error sending push notification: {str(e)}")
        print(traceback.format_exc())
        return False

def log_notification_history(customer_id, recipient_id, notification_type, subject, body, delivery_status, priority, sent_by):
    """Log notification to history table"""
    try:
        notification_id = f"notif_{int(datetime.utcnow().timestamp() * 1000)}"
        
        item = {
            'customer_id': customer_id,
            'notificationId': notification_id,
            'userId': recipient_id,
            'notificationType': notification_type,
            'subject': subject,
            'body': body,
            'status': 'unread',
            'priority': priority,
            'deliveryStatus': delivery_status,
            'sentAt': datetime.utcnow().isoformat(),
            'sentBy': sent_by
        }
        
        NOTIFICATION_HISTORY_TABLE.put_item(Item=item)
        print(f"Logged notification to history: {notification_id}")
    except Exception as e:
        print(f"Error logging notification history: {str(e)}")

def format_email_html(subject, body, data):
    """Format email with HTML template"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>{subject}</title>
    </head>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #2c3e50;">{subject}</h2>
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px;">
                {body}
            </div>
            <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #dee2e6; font-size: 12px; color: #6c757d;">
                <p>You're receiving this email based on your notification preferences.</p>
                <p>To update your preferences, visit your settings.</p>
            </div>
        </div>
    </body>
    </html>
    """
