# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Custom Report Generator
Generates custom reports based on event logs
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
s3 = boto3.client('s3')
EVENTS_LOG_TABLE = dynamodb.Table('EventsLog')
REPORTS_TABLE = dynamodb.Table('Reports')
REPORTS_BUCKET = 'provider-manager-reports'




@tracked
def lambda_handler(event, context):
    """
    Generate custom reports
    POST /reports/custom - Create report
    GET /reports/custom - List reports
    GET /reports/custom/{reportId} - Get report
    DELETE /reports/custom/{reportId} - Delete report
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
            return create_report(event, user_context)
        elif http_method == 'GET':
            path_params = event.get('pathParameters', {})
            if path_params.get('reportId'):
                return get_report(event, user_context)
            else:
                return list_reports(event, user_context)
        elif http_method == 'DELETE':
            return delete_report(event, user_context)
        else:
            return create_response(405, False, error="Method not allowed")
            
    except Exception as e:
        print(f"Error in custom report generator: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to process request: {str(e)}")

def create_report(event, user_context):
    """Create a new custom report"""
    import uuid
    from boto3.dynamodb.conditions import Key
    
    if isinstance(event.get('body'), str):
        body = json.loads(event['body'])
    else:
        body = event.get('body', {})
    
    customer_id = query_params.get('customer_id') or user_context['customer_id']
    if not customer_id:
        return create_response(400, False, error="Missing customer_id")
    
    report_id = str(uuid.uuid4())
    current_time = datetime.utcnow().isoformat()
    
    print(f"Generating report for company: {customer_id}")
    
    # Query events
    response = EVENTS_LOG_TABLE.query(
        KeyConditionExpression=Key('customer_id').eq(customer_id)
    )
    
    events = response.get('Items', [])
    
    # Generate report data
    report_data = {
        'total_events': len(events),
        'events': events[:1000]  # Limit to 1000 events
    }
    
    # Store report metadata
    report_record = {
        'customer_id': customer_id,
        'reportId': report_id,
        'reportType': body.get('reportType', 'custom'),
        'status': 'completed',
        'createdAt': current_time,
        'createdBy': user_context['user_id'] or 'system'
    }
    
    REPORTS_TABLE.put_item(Item=report_record)
    
    print(f"Report created: {report_id}")
    
    return create_response(201, True, {
        'report': report_record,
        'data': report_data,
        'message': 'Report generated successfully'
    })

def list_reports(event, user_context):
    """List all reports for a company"""
    from boto3.dynamodb.conditions import Key
    
    query_params = event.get('queryStringParameters', {}) or {}
    customer_id = query_params.get('customer_id') or user_context['customer_id']
    
    if not customer_id:
        return create_response(400, False, error="Missing customer_id")
    
    response = REPORTS_TABLE.query(
        KeyConditionExpression=Key('customer_id').eq(customer_id)
    )
    
    reports = response.get('Items', [])
    
    print(f"Found {len(reports)} reports for company {customer_id}")
    
    return create_response(200, True, {
        'reports': reports,
        'count': len(reports)
    })

def get_report(event, user_context):
    """Get a specific report"""
    path_params = event.get('pathParameters', {})
    report_id = path_params.get('reportId')
    
    query_params = event.get('queryStringParameters', {}) or {}
    customer_id = query_params.get('customer_id') or user_context['customer_id']
    
    if not customer_id or not report_id:
        return create_response(400, False, error="Missing customer_id or reportId")
    
    response = REPORTS_TABLE.get_item(
        Key={'customer_id': customer_id, 'reportId': report_id}
    )
    
    if 'Item' not in response:
        return create_response(404, False, error="Report not found")
    
    return create_response(200, True, {'report': response['Item']})

def delete_report(event, user_context):
    """Delete a report"""
    path_params = event.get('pathParameters', {})
    report_id = path_params.get('reportId')
    
    query_params = event.get('queryStringParameters', {}) or {}
    customer_id = query_params.get('customer_id') or user_context['customer_id']
   
    if not customer_id or not report_id:
        return create_response(400, False, error="Missing customer_id or reportId")
    
    REPORTS_TABLE.delete_item(
        Key={'customer_id': customer_id, 'reportId': report_id}
    )
    
    print(f"Deleted report: {report_id}")
    
    return create_response(200, True, {'message': 'Report deleted successfully'})
