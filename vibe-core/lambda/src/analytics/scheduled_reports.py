# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Scheduled Reports
Manages scheduled report generation
Supports AWS API Gateway V2 with header-based authentication
"""
import json
import boto3
import traceback
from datetime import datetime
from decimal import Decimal
from utils.track_api_call import tracked
from utils.lambda_utils import extract_user_context,decimal_default,create_response

dynamodb = boto3.resource('dynamodb')
SCHEDULED_REPORTS_TABLE = dynamodb.Table('ScheduledReports')




@tracked
def lambda_handler(event, context):
    """
    Manage scheduled reports
    POST /reports/scheduled - Create schedule
    GET /reports/scheduled - List schedules
    PUT /reports/scheduled/{scheduleId} - Update schedule
    DELETE /reports/scheduled/{scheduleId} - Delete schedule
    """
    print(f"Event: {json.dumps(event, default=decimal_default)}")
    print(f"Context: {context}")
    
    try:
        http_method = event.get('requestContext', {}).get('http', {}).get('method')
        
        if http_method == 'OPTIONS':
            return create_response(200, True)
        
        user_context = extract_user_context(event)
        print(f"User context: {json.dumps(user_context)}")
        
        if http_method == 'POST':
            return create_schedule(event, user_context)
        elif http_method == 'GET':
            return list_schedules(event, user_context)
        elif http_method == 'PUT':
            return update_schedule(event, user_context)
        elif http_method == 'DELETE':
            return delete_schedule(event, user_context)
        else:
            return create_response(405, False, error="Method not allowed")
            
    except Exception as e:
        print(f"Error in scheduled reports: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to process schedule: {str(e)}")

def create_schedule(event, user_context):
    """Create report schedule"""
    import uuid
    
    if isinstance(event.get('body'), str):
        body = json.loads(event['body'])
    else:
        body = event.get('body', {})
    
    customer_id = query_params.get('customer_id') or user_context['customer_id']
    
    if not customer_id:
        return create_response(400, False, error="Missing customer_id")
    
    schedule_id = str(uuid.uuid4())
    current_time = datetime.utcnow().isoformat()
    
    schedule = {
        'customer_id': customer_id,
        'scheduleId': schedule_id,
        'frequency': body.get('frequency', 'daily'),
        'reportType': body.get('reportType', 'summary'),
        'createdAt': current_time,
        'createdBy': user_context['user_id'] or 'system'
    }
    
    SCHEDULED_REPORTS_TABLE.put_item(Item=schedule)
    
    print(f"Schedule created: {schedule_id}")
    
    return create_response(201, True, {
        'schedule': schedule,
        'message': 'Schedule created successfully'
    })

def list_schedules(event, user_context):
    """List report schedules"""
    from boto3.dynamodb.conditions import Key
    
    query_params = event.get('queryStringParameters', {}) or {}
    customer_id = query_params.get('customer_id') or user_context['customer_id']
   
    if not customer_id:
        return create_response(400, False, error="Missing customer_id")
    
    response = SCHEDULED_REPORTS_TABLE.query(
        KeyConditionExpression=Key('customer_id').eq(customer_id)
    )
    
    schedules = response.get('Items', [])
    
    return create_response(200, True, {
        'schedules': schedules,
        'count': len(schedules)
    })

def update_schedule(event, user_context):
    """Update report schedule"""
    path_params = event.get('pathParameters', {})
    schedule_id = path_params.get('scheduleId')
    
    if isinstance(event.get('body'), str):
        body = json.loads(event['body'])
    else:
        body = event.get('body', {})
    
    customer_id = query_params.get('customer_id') or user_context['customer_id']
    
    if not customer_id or not schedule_id:
        return create_response(400, False, error="Missing customer_id or scheduleId")
    
    update_expr = "SET modifiedAt = :timestamp"
    expr_values = {':timestamp': datetime.utcnow().isoformat()}
    
    if 'frequency' in body:
        update_expr += ", frequency = :frequency"
        expr_values[':frequency'] = body['frequency']
    
    response = SCHEDULED_REPORTS_TABLE.update_item(
        Key={'customer_id': customer_id, 'scheduleId': schedule_id},
        UpdateExpression=update_expr,
        ExpressionAttributeValues=expr_values,
        ReturnValues='ALL_NEW'
    )
    
    return create_response(200, True, {
        'schedule': response['Attributes'],
        'message': 'Schedule updated successfully'
    })

def delete_schedule(event, user_context):
    """Delete report schedule"""
    path_params = event.get('pathParameters', {})
    schedule_id = path_params.get('scheduleId')
    
    query_params = event.get('queryStringParameters', {}) or {}
    customer_id = query_params.get('customer_id') or user_context['customer_id']
    
    if not customer_id or not schedule_id:
        return create_response(400, False, error="Missing customer_id or scheduleId")
    
    SCHEDULED_REPORTS_TABLE.delete_item(
        Key={'customer_id': customer_id, 'scheduleId': schedule_id}
    )
    
    return create_response(200, True, {'message': 'Schedule deleted successfully'})
