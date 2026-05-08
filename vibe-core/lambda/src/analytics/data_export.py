# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Data Export
Exports data to various formats
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
EXPORT_JOBS_TABLE = dynamodb.Table('ExportJobs')
REPORTS_BUCKET = 'provider-manager-reports'




@tracked
def lambda_handler(event, context):
    """
    Export data
    POST /export - Create export job
    GET /export/{jobId} - Get export job
    GET /export - List export jobs
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
            return create_export(event, user_context)
        elif http_method == 'GET':
            path_params = event.get('pathParameters', {})
            if path_params.get('jobId'):
                return get_export(event, user_context)
            else:
                return list_exports(event, user_context)
        else:
            return create_response(405, False, error="Method not allowed")
            
    except Exception as e:
        print(f"Error in data export: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to process export: {str(e)}")

def create_export(event, user_context):
    """Create export job"""
    import uuid
    
    if isinstance(event.get('body'), str):
        body = json.loads(event['body'])
    else:
        body = event.get('body', {})
    
    customer_id = query_params.get('customer_id') or user_context['customer_id']
    if not customer_id:
        return create_response(400, False, error="Missing customer_id")
    
    job_id = str(uuid.uuid4())
    current_time = datetime.utcnow().isoformat()
    
    export_job = {
        'customer_id': customer_id,
        'jobId': job_id,
        'status': 'completed',
        'exportType': body.get('exportType', 'csv'),
        'createdAt': current_time,
        'createdBy': user_context['user_id'] or 'system'
    }
    
    EXPORT_JOBS_TABLE.put_item(Item=export_job)
    
    print(f"Export job created: {job_id}")
    
    return create_response(201, True, {
        'job': export_job,
        'message': 'Export job created successfully'
    })

def get_export(event, user_context):
    """Get export job"""
    path_params = event.get('pathParameters', {})
    job_id = path_params.get('jobId')
    
    query_params = event.get('queryStringParameters', {}) or {}
    customer_id = query_params.get('customer_id') or user_context['customer_id']
    
    if not customer_id or not job_id:
        return create_response(400, False, error="Missing customer_id or jobId")
    
    response = EXPORT_JOBS_TABLE.get_item(
        Key={'customer_id': customer_id, 'jobId': job_id}
    )
    
    if 'Item' not in response:
        return create_response(404, False, error="Export job not found")
    
    return create_response(200, True, {'job': response['Item']})

def list_exports(event, user_context):
    """List export jobs"""
    from boto3.dynamodb.conditions import Key
    
    query_params = event.get('queryStringParameters', {}) or {}
    customer_id = query_params.get('customer_id') or user_context['customer_id']
   
    if not customer_id:
        return create_response(400, False, error="Missing customer_id")
    
    response = EXPORT_JOBS_TABLE.query(
        KeyConditionExpression=Key('customer_id').eq(customer_id)
    )
    
    jobs = response.get('Items', [])
    
    print(f"Found {len(jobs)} export jobs for company {customer_id}")
    
    return create_response(200, True, {
        'jobs': jobs,
        'count': len(jobs)
    })
