# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Lambda function for managing user notification preferences
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
dynamodb = boto3.resource('dynamodb')

# Hardcoded table name
PREFERENCES_TABLE = dynamodb.Table('NotificationPreferencesTable')

@tracked
def lambda_handler(event, context):
    """
    Manage notification preferences for users
    GET /notifications/preferences - Get preferences
    PUT /notifications/preferences - Update preferences
    POST /notifications/preferences - Create preferences
    """
    
    # Log comprehensive request context
    print(f"Event: {json.dumps(event)}")
    print(f"Context: {context}")
    
    try:
        # Get HTTP method
        http_method = event.get('requestContext', {}).get('http', {}).get('method')
        
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
            return get_preferences(user_id, customer_id)
        elif http_method == 'PUT':
            body = json.loads(event['body']) if isinstance(event.get('body'), str) else event.get('body', {})
            return update_preferences(user_id, customer_id, body, user_context)
        elif http_method == 'POST':
            body = json.loads(event['body']) if isinstance(event.get('body'), str) else event.get('body', {})
            return create_preferences(user_id, customer_id, body, user_context)
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

def get_preferences(user_id, customer_id):
    """Get notification preferences for a user"""
    try:
        response = PREFERENCES_TABLE.get_item(
            Key={
                'customer_id': customer_id,
                'userId': user_id
            }
        )
        
        if 'Item' in response:
            print(f"Retrieved preferences for user {user_id}")
            return create_response(200, True, response['Item'])
        else:
            # Return default preferences if none exist
            default_preferences = get_default_preferences(customer_id, user_id)
            print(f"Returning default preferences for user {user_id}")
            return create_response(200, True, default_preferences)
    except Exception as e:
        print(f"Error getting preferences: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to get preferences: {str(e)}")

def get_default_preferences(customer_id, user_id):
    """Return default notification preferences"""
    return {
        'customer_id': customer_id,
        'userId': user_id,
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
        'frequency': 'immediate',  # immediate, daily_digest, weekly_digest
        'quietHours': {
            'enabled': False,
            'start': '22:00',
            'end': '08:00'
        }
    }

def create_preferences(user_id, customer_id, preferences, user_context):
    """Create new notification preferences"""
    try:
        item = {
            'customer_id': customer_id,
            'userId': user_id,
            'emailNotifications': preferences.get('emailNotifications', {}),
            'smsNotifications': preferences.get('smsNotifications', {}),
            'pushNotifications': preferences.get('pushNotifications', {}),
            'frequency': preferences.get('frequency', 'immediate'),
            'quietHours': preferences.get('quietHours', {'enabled': False}),
            'createdAt': datetime.utcnow().isoformat(),
            'updatedAt': datetime.utcnow().isoformat(),
            'createdBy': user_id,
            'updatedBy': user_id
        }
        
        PREFERENCES_TABLE.put_item(Item=item)
        print(f"Created preferences for user {user_id}")
        
        return create_response(201, True, {
            'preferences': item,
            'message': 'Preferences created successfully'
        })
    except Exception as e:
        print(f"Error creating preferences: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to create preferences: {str(e)}")

def update_preferences(user_id, customer_id, updates, user_context):
    """Update existing notification preferences"""
    try:
        # Build update expression dynamically
        update_expr = "SET updatedAt = :updatedAt, updatedBy = :updatedBy"
        expr_values = {
            ':updatedAt': datetime.utcnow().isoformat(),
            ':updatedBy': user_id
        }
        
        if 'emailNotifications' in updates:
            update_expr += ", emailNotifications = :email"
            expr_values[':email'] = updates['emailNotifications']
        
        if 'smsNotifications' in updates:
            update_expr += ", smsNotifications = :sms"
            expr_values[':sms'] = updates['smsNotifications']
        
        if 'pushNotifications' in updates:
            update_expr += ", pushNotifications = :push"
            expr_values[':push'] = updates['pushNotifications']
        
        if 'frequency' in updates:
            if updates['frequency'] not in ['immediate', 'daily_digest', 'weekly_digest']:
                return create_response(400, False, 
                    error="Invalid frequency. Must be: immediate, daily_digest, or weekly_digest")
            update_expr += ", frequency = :freq"
            expr_values[':freq'] = updates['frequency']
        
        if 'quietHours' in updates:
            update_expr += ", quietHours = :quiet"
            expr_values[':quiet'] = updates['quietHours']
        
        response = PREFERENCES_TABLE.update_item(
            Key={
                'customer_id': customer_id,
                'userId': user_id
            },
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
            ReturnValues='ALL_NEW'
        )
        
        print(f"Updated preferences for user {user_id}")
        
        return create_response(200, True, {
            'preferences': response['Attributes'],
            'message': 'Preferences updated successfully'
        })
    except Exception as e:
        print(f"Error updating preferences: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to update preferences: {str(e)}")
