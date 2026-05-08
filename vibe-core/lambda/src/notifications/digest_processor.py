# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Lambda function for processing notification digests (daily/weekly summaries)
Triggered by CloudWatch Events on a schedule
"""
import json
import boto3
import traceback
from datetime import datetime, timedelta
from collections import defaultdict
from decimal import Decimal
from utils.track_api_call import tracked
from utils.lambda_utils import extract_user_context,decimal_default,create_response

# AWS Clients
dynamodb = boto3.resource('dynamodb')
ses = boto3.client('ses')

# Hardcoded table names
DIGEST_QUEUE_TABLE = dynamodb.Table('DigestQueueTable')
PREFERENCES_TABLE = dynamodb.Table('NotificationPreferencesTable')

@tracked
def lambda_handler(event, context):
    """
    Process and send notification digests
    Scheduled to run daily for daily digests, weekly for weekly digests
    Event payload: {"digestType": "daily"} or {"digestType": "weekly"}
    """
    
    # Log comprehensive request context
    print(f"Event: {json.dumps(event, default=decimal_default)}")
    print(f"Context: {context}")
    
    try:
        # Determine digest type from event (daily or weekly)
        digest_type = event.get('digestType', 'daily')
        
        print(f"Processing {digest_type} digests")
        
        if digest_type == 'daily':
            process_daily_digests()
        elif digest_type == 'weekly':
            process_weekly_digests()
        else:
            print(f"Invalid digest type: {digest_type}")
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'success': False,
                    'error': f'Invalid digest type: {digest_type}',
                    'timestamp': datetime.utcnow().isoformat()
                })
            }
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'message': f'{digest_type} digests processed',
                'timestamp': datetime.utcnow().isoformat()
            })
        }
        
    except Exception as e:
        print(f"Error processing digests: {str(e)}")
        print(traceback.format_exc())
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            })
        }

def process_daily_digests():
    """Process and send daily notification digests"""
    try:
        # Get all users with daily digest preference
        users = get_users_by_preference('daily_digest')
        
        print(f"Processing daily digests for {len(users)} users")
        
        for user in users:
            customer_id = user['customer_id']
            user_id = user['userId']
            
            # Get queued notifications for this user from last 24 hours
            notifications = get_queued_notifications(customer_id, user_id, hours=24)
            
            if notifications:
                # Group notifications by type
                grouped = group_notifications(notifications)
                
                # Send digest email
                send_digest_email(user, grouped, 'daily')
                
                # Clean up processed notifications
                cleanup_processed_notifications(notifications)
            else:
                print(f"No notifications to digest for user {user_id}")
        
        print("Daily digest processing completed")
        
    except Exception as e:
        print(f"Error processing daily digests: {str(e)}")
        print(traceback.format_exc())
        raise

def process_weekly_digests():
    """Process and send weekly notification digests"""
    try:
        # Get all users with weekly digest preference
        users = get_users_by_preference('weekly_digest')
        
        print(f"Processing weekly digests for {len(users)} users")
        
        for user in users:
            customer_id = user['customer_id']
            user_id = user['userId']
            
            # Get queued notifications for this user from last 7 days
            notifications = get_queued_notifications(customer_id, user_id, hours=168)
            
            if notifications:
                # Group notifications by type
                grouped = group_notifications(notifications)
                
                # Send digest email
                send_digest_email(user, grouped, 'weekly')
                
                # Clean up processed notifications
                cleanup_processed_notifications(notifications)
            else:
                print(f"No notifications to digest for user {user_id}")
        
        print("Weekly digest processing completed")
        
    except Exception as e:
        print(f"Error processing weekly digests: {str(e)}")
        print(traceback.format_exc())
        raise

def get_users_by_preference(preference):
    """Get all users with specific digest preference"""
    users = []
    
    try:
        from boto3.dynamodb.conditions import Key
        
        response = PREFERENCES_TABLE.scan(
            FilterExpression=Key('frequency').eq(preference)
        )
        
        users = response.get('Items', [])
        
        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = PREFERENCES_TABLE.scan(
                FilterExpression=Key('frequency').eq(preference),
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            users.extend(response.get('Items', []))
        
        print(f"Found {len(users)} users with {preference} preference")
        
    except Exception as e:
        print(f"Error getting users by preference: {str(e)}")
        print(traceback.format_exc())
    
    return users

def get_queued_notifications(customer_id, user_id, hours=24):
    """Get queued notifications for a user within specified time window"""
    try:
        cutoff_time = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        
        from boto3.dynamodb.conditions import Key
        
        response = DIGEST_QUEUE_TABLE.query(
            KeyConditionExpression=Key('customer_id').eq(customer_id) & Key('timestamp').gt(cutoff_time),
            FilterExpression=Key('userId').eq(user_id)
        )
        
        notifications = response.get('Items', [])
        print(f"Retrieved {len(notifications)} queued notifications for user {user_id}")
        
        return notifications
        
    except Exception as e:
        print(f"Error getting queued notifications: {str(e)}")
        print(traceback.format_exc())
        return []

def group_notifications(notifications):
    """Group notifications by type and priority"""
    grouped = defaultdict(lambda: defaultdict(list))
    
    for notif in notifications:
        message = notif.get('message', {})
        ntype = message.get('type', 'other')
        priority = message.get('priority', 'normal')
        
        grouped[ntype][priority].append(message)
    
    return dict(grouped)

def send_digest_email(user, grouped_notifications, digest_type):
    """Send digest email to user"""
    try:
        user_email = user.get('email', f"{user['userId']}@example.com")
        from_email = user.get('fromEmail', 'noreply@yourdomain.com')
        
        # Build HTML email
        subject = f"Your {digest_type.capitalize()} Notification Digest"
        html_body = build_digest_html(grouped_notifications, digest_type)
        text_body = build_digest_text(grouped_notifications, digest_type)
        
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
                        'Data': html_body,
                        'Charset': 'UTF-8'
                    },
                    'Text': {
                        'Data': text_body,
                        'Charset': 'UTF-8'
                    }
                }
            }
        )
        
        print(f"Digest sent to {user_email}: {response['MessageId']}")
        
    except Exception as e:
        print(f"Error sending digest email: {str(e)}")
        print(traceback.format_exc())

def build_digest_html(grouped_notifications, digest_type):
    """Build HTML content for digest email"""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>{digest_type.capitalize()} Digest</title>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
            h2 {{ color: #34495e; margin-top: 30px; }}
            .notification-group {{ background-color: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 5px; }}
            .urgent {{ border-left: 4px solid #e74c3c; }}
            .high {{ border-left: 4px solid #f39c12; }}
            .normal {{ border-left: 4px solid #3498db; }}
            .low {{ border-left: 4px solid #95a5a6; }}
            .notification-item {{ margin: 10px 0; padding: 10px; background-color: white; border-radius: 3px; }}
            .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #dee2e6; font-size: 12px; color: #6c757d; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Your {digest_type.capitalize()} Notification Digest</h1>
            <p>Here's a summary of your notifications:</p>
    """
    
    # Add notifications by type
    for ntype, priorities in grouped_notifications.items():
        html += f"<h2>{format_notification_type(ntype)}</h2>"
        
        for priority in ['urgent', 'high', 'normal', 'low']:
            if priority in priorities:
                notifs = priorities[priority]
                html += f'<div class="notification-group {priority}">'
                html += f'<strong>{priority.capitalize()} Priority</strong> ({len(notifs)} notifications)'
                
                for notif in notifs[:5]:  # Show up to 5 per priority
                    html += f'''
                    <div class="notification-item">
                        <strong>{notif.get('subject', 'No subject')}</strong><br>
                        {notif.get('body', '')[:150]}...
                    </div>
                    '''
                
                if len(notifs) > 5:
                    html += f'<p><em>...and {len(notifs) - 5} more</em></p>'
                
                html += '</div>'
    
    html += """
            <div class="footer">
                <p>This is your scheduled notification digest.</p>
                <p>To change your notification preferences, visit your settings.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html

def build_digest_text(grouped_notifications, digest_type):
    """Build plain text content for digest email"""
    text = f"{digest_type.upper()} NOTIFICATION DIGEST\n"
    text += "=" * 50 + "\n\n"
    
    for ntype, priorities in grouped_notifications.items():
        text += f"\n{format_notification_type(ntype).upper()}\n"
        text += "-" * 30 + "\n"
        
        for priority, notifs in priorities.items():
            text += f"\n{priority.capitalize()} Priority ({len(notifs)} notifications):\n"
            
            for notif in notifs[:5]:
                text += f"  • {notif.get('subject', 'No subject')}\n"
                text += f"    {notif.get('body', '')[:100]}...\n\n"
            
            if len(notifs) > 5:
                text += f"  ...and {len(notifs) - 5} more\n"
    
    text += "\n" + "=" * 50 + "\n"
    text += "To change your notification preferences, visit your settings.\n"
    
    return text

def format_notification_type(ntype):
    """Format notification type for display"""
    type_map = {
        'appointments': 'Appointments',
        'tasks': 'Tasks',
        'payments': 'Payments',
        'disputes': 'Disputes',
        'systemUpdates': 'System Updates',
        'other': 'Other Notifications'
    }
    return type_map.get(ntype, ntype.capitalize())

def cleanup_processed_notifications(notifications):
    """Remove processed notifications from queue"""
    try:
        with DIGEST_QUEUE_TABLE.batch_writer() as batch:
            for notif in notifications:
                batch.delete_item(
                    Key={
                        'customer_id': notif['customer_id'],
                        'timestamp': notif['timestamp']
                    }
                )
        print(f"Cleaned up {len(notifications)} processed notifications")
    except Exception as e:
        print(f"Error cleaning up notifications: {str(e)}")
        print(traceback.format_exc())
