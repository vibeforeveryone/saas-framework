# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Lambda function for managing notification history and tracking
Supports AWS API Gateway V2 with header-based authentication
"""
import json
import boto3
import traceback
from datetime import datetime, timedelta
from decimal import Decimal
from boto3.dynamodb.conditions import Key
from utils.track_api_call import tracked
from utils.lambda_utils import extract_user_context,decimal_default,create_response

# AWS Clients
dynamodb = boto3.resource('dynamodb')

# Hardcoded table name
HISTORY_TABLE = dynamodb.Table('NotificationHistoryTable')

@tracked
def lambda_handler(event, context):
    """
    Manage notification history
    GET /notifications/history - Get notification history
    GET /notifications/history/unread - Get unread notifications
    GET /notifications/history/stats - Get notification statistics
    POST /notifications/history - Create notification record
    PATCH /notifications/history/{id} - Update notification (mark as read, archive)
    DELETE /notifications/history/{id} - Delete notification
    """
    
    # Log comprehensive request context
    print(f"Event: {json.dumps(event)}")
    print(f"Context: {context}")
    
    try:
        # Get HTTP method
        http_method = event.get('requestContext', {}).get('http', {}).get('method')
        path = event.get('rawPath', '') or event.get('path', '')
        
        # Handle OPTIONS preflight request
        if http_method == 'OPTIONS':
            return create_response(200, True)
        
        # Extract user context from headers
        user_context = extract_user_context(event)
        print(f"User context: {json.dumps(user_context)}")
        
        user_id = user_context['user_id']
        customer_id = user_context['provider_id']
        
        if not user_id or not customer_id:
            return create_response(401, False, error="User authentication required")
        
        if http_method == 'GET':
            query_params = event.get('queryStringParameters', {}) or {}
            
            if path.endswith('/unread'):
                return get_unread_notifications(user_id, customer_id)
            elif path.endswith('/stats'):
                return get_notification_stats(user_id, customer_id)
            else:
                return get_notification_history(user_id, customer_id, query_params)
        
        elif http_method == 'POST':
            body = json.loads(event['body']) if isinstance(event.get('body'), str) else event.get('body', {})
            return create_notification_record(user_id, customer_id, body, user_context)
        
        elif http_method == 'PATCH':
            path_params = event.get('pathParameters', {})
            notification_id = path_params.get('id')
            if not notification_id:
                return create_response(400, False, error="Missing notification ID")
            body = json.loads(event['body']) if isinstance(event.get('body'), str) else event.get('body', {})
            return update_notification(user_id, customer_id, notification_id, body)
        
        elif http_method == 'DELETE':
            path_params = event.get('pathParameters', {})
            notification_id = path_params.get('id')
            if not notification_id:
                return create_response(400, False, error="Missing notification ID")
            return delete_notification(user_id, customer_id, notification_id)
        
        else:
            return create_response(405, False, error='Method not allowed')
            
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {str(e)}")
        print(traceback.format_exc())
        return create_response(400, False, error="Invalid JSON in request body")
    except Exception as e:
        print(f"Error: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=str(e))

def get_notification_history(user_id, customer_id, query_params):
    """Get notification history with optional filters"""
    try:
        limit = int(query_params.get('limit', 50))
        notification_type = query_params.get('type')
        days_back = int(query_params.get('days', 30))
        
        # Calculate date filter
        start_date = (datetime.utcnow() - timedelta(days=days_back)).isoformat()
        
        # Build query parameters
        query_kwargs = {
            'IndexName': 'UserNotificationsIndex',
            'KeyConditionExpression': Key('userId').eq(user_id) & Key('sentAt').gt(start_date),
            'Limit': limit,
            'ScanIndexForward': False  # Most recent first
        }
        
        # Add filter for notification type if specified
        if notification_type:
            query_kwargs['FilterExpression'] = Key('notificationType').eq(notification_type)
        
        response = HISTORY_TABLE.query(**query_kwargs)
        
        print(f"Retrieved {len(response.get('Items', []))} notification history records")
        
        return create_response(200, True, {
            'notifications': response.get('Items', []),
            'count': response.get('Count', 0)
        })
    except Exception as e:
        print(f"Error getting notification history: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to get notification history: {str(e)}")

def get_unread_notifications(user_id, customer_id):
    """Get unread notifications for a user"""
    try:
        response = HISTORY_TABLE.query(
            IndexName='UserNotificationsIndex',
            KeyConditionExpression=Key('userId').eq(user_id),
            FilterExpression=Key('status').eq('unread'),
            Limit=100
        )
        
        print(f"Retrieved {len(response.get('Items', []))} unread notifications")
        
        return create_response(200, True, {
            'notifications': response.get('Items', []),
            'count': response.get('Count', 0)
        })
    except Exception as e:
        print(f"Error getting unread notifications: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to get unread notifications: {str(e)}")

def get_notification_stats(user_id, customer_id):
    """Get notification statistics for a user"""
    try:
        # Get last 30 days of notifications
        start_date = (datetime.utcnow() - timedelta(days=30)).isoformat()
        
        response = HISTORY_TABLE.query(
            IndexName='UserNotificationsIndex',
            KeyConditionExpression=Key('userId').eq(user_id) & Key('sentAt').gt(start_date)
        )
        
        notifications = response.get('Items', [])
        
        # Calculate statistics
        stats = {
            'total': len(notifications),
            'unread': sum(1 for n in notifications if n.get('status') == 'unread'),
            'byType': {},
            'byChannel': {
                'email': 0,
                'sms': 0,
                'push': 0
            },
            'last30Days': len(notifications)
        }
        
        for notification in notifications:
            # Count by type
            ntype = notification.get('notificationType', 'other')
            stats['byType'][ntype] = stats['byType'].get(ntype, 0) + 1
            
            # Count by channel
            delivery_status = notification.get('deliveryStatus', {})
            for channel, status in delivery_status.items():
                if status == 'sent' and channel in stats['byChannel']:
                    stats['byChannel'][channel] += 1
        
        print(f"Calculated statistics for user {user_id}")
        
        return create_response(200, True, stats)
    except Exception as e:
        print(f"Error getting notification stats: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to get notification stats: {str(e)}")

def create_notification_record(user_id, customer_id, data, user_context):
    """Create a notification history record"""
    try:
        notification_id = f"notif_{int(datetime.utcnow().timestamp() * 1000)}"
        
        item = {
            'customer_id': customer_id,
            'notificationId': notification_id,
            'userId': user_id,
            'notificationType': data.get('type'),
            'subject': data.get('subject'),
            'body': data.get('body'),
            'channels': data.get('channels', []),  # email, sms, push
            'status': 'unread',
            'priority': data.get('priority', 'normal'),
            'metadata': data.get('metadata', {}),
            'sentAt': datetime.utcnow().isoformat(),
            'deliveryStatus': {
                'email': data.get('emailStatus', 'pending'),
                'sms': data.get('smsStatus', 'pending'),
                'push': data.get('pushStatus', 'pending')
            },
            'createdBy': user_context['user_id']
        }
        
        HISTORY_TABLE.put_item(Item=item)
        print(f"Created notification record: {notification_id}")
        
        return create_response(201, True, {
            'notification': item,
            'message': 'Notification record created successfully'
        })
    except Exception as e:
        print(f"Error creating notification record: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to create notification record: {str(e)}")

def update_notification(user_id, customer_id, notification_id, updates):
    """Update notification status (read/unread, archived, etc)"""
    try:
        update_expr = "SET "
        expr_values = {}
        expr_names = {}
        update_parts = []
        
        if 'status' in updates:
            update_parts.append("#status = :status")
            expr_names['#status'] = 'status'
            expr_values[':status'] = updates['status']
            
            if updates['status'] == 'read':
                update_parts.append("readAt = :readAt")
                expr_values[':readAt'] = datetime.utcnow().isoformat()
        
        if 'archived' in updates:
            update_parts.append("archived = :archived")
            expr_values[':archived'] = updates['archived']
            
            if updates['archived']:
                update_parts.append("archivedAt = :archivedAt")
                expr_values[':archivedAt'] = datetime.utcnow().isoformat()
        
        if not update_parts:
            return create_response(400, False, error='No valid updates provided')
        
        update_expr += ", ".join(update_parts)
        
        response = HISTORY_TABLE.update_item(
            Key={
                'customer_id': customer_id,
                'notificationId': notification_id
            },
            UpdateExpression=update_expr,
            ExpressionAttributeValues={**expr_values, ':uid': user_id},
            ExpressionAttributeNames=expr_names if expr_names else None,
            ConditionExpression='userId = :uid',
            ReturnValues='ALL_NEW'
        )
        
        print(f"Updated notification: {notification_id}")
        
        return create_response(200, True, {
            'notification': response['Attributes'],
            'message': 'Notification updated successfully'
        })
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        print(f"Unauthorized update attempt for notification {notification_id}")
        return create_response(403, False, error='Not authorized to update this notification')
    except Exception as e:
        print(f"Error updating notification: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to update notification: {str(e)}")

def delete_notification(user_id, customer_id, notification_id):
    """Delete a notification from history"""
    try:
        HISTORY_TABLE.delete_item(
            Key={
                'customer_id': customer_id,
                'notificationId': notification_id
            },
            ConditionExpression='userId = :uid',
            ExpressionAttributeValues={':uid': user_id}
        )
        
        print(f"Deleted notification: {notification_id}")
        
        return create_response(200, True, {
            'message': 'Notification deleted successfully'
        })
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        print(f"Unauthorized delete attempt for notification {notification_id}")
        return create_response(403, False, error='Not authorized to delete this notification')
    except Exception as e:
        print(f"Error deleting notification: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to delete notification: {str(e)}")
