# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Event Logger
Triggered by DynamoDB Streams from source tables (Customers, User,
PaymentTransaction, Dispute). Writes a normalized record to EventsLog
for use by DashboardHome, analytics, and reporting screens.

Supports three event sources:
  - DynamoDB Streams  (primary — wired via template EventSourceMapping)
  - SNS               (future use)
  - SQS               (future use)
  - Direct invocation (testing / manual)

NOTE: This is internal infrastructure. It must NOT use @tracked —
      the decorator expects HTTP API Gateway events, not stream Records.
"""
import json
import boto3
import traceback
import hashlib
import os
import logging
from datetime import datetime
from decimal import Decimal

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

dynamodb   = boto3.resource('dynamodb')
cloudwatch = boto3.client('cloudwatch')

# ── Bug 1 fixed: was 'EventsLogTable', actual table name is 'EventsLog' ──────
EVENTS_TABLE = dynamodb.Table('EventsLog')


# ── Table name → resource type mapping ───────────────────────────────────────
TABLE_RESOURCE_MAP = {
    'Customers':            'customer',
    'User':                 'user',
    'PaymentTransaction':   'transaction',
    'Dispute':              'dispute',
    'UserRole':             'user_role',
    'UserFeature':          'user_feature',
    'CustomerLicenseHistory': 'license_history',
}


# =============================================================================
# Lambda entry point
# =============================================================================

def lambda_handler(event, context):
    """
    Process stream/SNS/SQS/direct events and write to EventsLog.
    Never decorated with @tracked — this is not a billable HTTP endpoint.
    """
    logger.info(f"Event received: {json.dumps(event, default=str)}")

    try:
        if 'Records' in event:
            for record in event['Records']:
                if 'Sns' in record:
                    process_event(json.loads(record['Sns']['Message']))
                elif 'dynamodb' in record:
                    process_dynamodb_stream_record(record)
                elif 'body' in record:
                    process_event(json.loads(record['body']))
        else:
            # Direct invocation (manual or test)
            process_event(event)

        logger.info("Event(s) logged successfully")
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'message': 'Events logged successfully',
                'timestamp': datetime.utcnow().isoformat()
            })
        }

    except Exception as e:
        logger.error(f"Error logging event: {str(e)}")
        logger.error(traceback.format_exc())
        # Return 200 so Lambda does not retry stream records indefinitely.
        # Individual record errors are already caught inside the helpers.
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            })
        }


# =============================================================================
# Stream record processor
# =============================================================================

def process_dynamodb_stream_record(record):
    """Convert a raw DynamoDB stream record into a normalised event dict."""
    try:
        event_name = record.get('eventName', '')  # INSERT | MODIFY | REMOVE

        action_map = {
            'INSERT': 'created',
            'MODIFY': 'updated',
            'REMOVE': 'deleted',
        }
        action = action_map.get(event_name, 'unknown')

        new_image = convert_dynamodb_json(
            record.get('dynamodb', {}).get('NewImage', {}))
        old_image = convert_dynamodb_json(
            record.get('dynamodb', {}).get('OldImage', {}))

        # customer_id may live on either image depending on INSERT/REMOVE
        customer_id = (new_image.get('customer_id') or
                       old_image.get('customer_id') or
                       'system')

        # user_id: check common field names across tables
        user_id = (new_image.get('modified_by') or
                   new_image.get('created_by') or
                   new_image.get('user_key') or
                   old_image.get('modified_by') or
                   'system')

        resource_type = determine_resource_type(record)
        resource_id   = extract_resource_id(new_image, old_image, resource_type)

        event_data = {
            'eventType':    'data_change',
            'customer_id':  customer_id,
            'userId':       user_id,
            'resourceType': resource_type,
            'resourceId':   resource_id,
            'action':       action,
            'metadata': {
                'changes': calculate_changes(old_image, new_image),
                'source':  'dynamodb_stream',
                'table':   get_table_name_from_arn(record),
            }
        }

        process_event(event_data)

    except Exception as e:
        logger.error(f"Error processing stream record: {str(e)}")
        logger.error(traceback.format_exc())
        # Don't re-raise — a single bad record should not block the whole batch


# =============================================================================
# Core event writer
# =============================================================================

def process_event(event_data):
    """Validate, enrich, and write a single event to EventsLog."""
    try:
        customer_id   = event_data.get('customer_id') or 'system'
        event_type    = event_data.get('eventType')   or 'unknown'
        user_id       = event_data.get('userId')      or 'system'
        resource_type = event_data.get('resourceType')
        resource_id   = event_data.get('resourceId')
        action        = event_data.get('action')
        metadata      = event_data.get('metadata', {})

        timestamp = datetime.utcnow()
        event_id  = generate_event_id(customer_id, timestamp)

        event_record = {
            'customer_id':  customer_id,
            'timestamp':    timestamp.isoformat(),
            'eventId':      event_id,
            'eventType':    event_type,
            'userId':       user_id,
            'resourceType': resource_type,
            'resourceId':   resource_id,
            'action':       action,
            'metadata':     metadata,
            'source':       event_data.get('source', 'api'),
            'ipAddress':    metadata.get('ipAddress'),
            'userAgent':    metadata.get('userAgent'),
            'sessionId':    metadata.get('sessionId'),
        }

        # Strip None values — DynamoDB rejects them
        event_record = {k: v for k, v in event_record.items() if v is not None}

        EVENTS_TABLE.put_item(Item=event_record)
        logger.info(f"Logged: {event_type}/{action} "
                    f"resource={resource_type}:{resource_id} "
                    f"customer={customer_id}")

        send_cloudwatch_metrics(event_type, action, customer_id)
        trigger_webhooks(customer_id, event_record)

    except Exception as e:
        logger.error(f"Error writing event to EventsLog: {str(e)}")
        logger.error(traceback.format_exc())
        raise


# =============================================================================
# Helper functions
# =============================================================================

def generate_event_id(customer_id: str, timestamp: datetime) -> str:
    unique = f"{customer_id}_{timestamp.isoformat()}_{os.urandom(8).hex()}"
    return hashlib.sha256(unique.encode()).hexdigest()[:16]


def get_table_name_from_arn(record) -> str:
    """
    Extract table name from DynamoDB stream record eventSourceARN.
    ARN format: arn:aws:dynamodb:region:account:table/TableName/stream/ts
    split('/') → ['...table', 'TableName', 'stream', 'ts']
    index 1 = TableName
    """
    try:
        arn = record.get('eventSourceARN', '')
        return arn.split('/')[1] if '/' in arn else 'unknown'
    except Exception:
        return 'unknown'


def determine_resource_type(record) -> str:
    table_name = get_table_name_from_arn(record)
    return TABLE_RESOURCE_MAP.get(table_name, table_name.lower())


def extract_resource_id(new_data: dict, old_data: dict, resource_type: str) -> str:
    """
    Return the primary key value for the changed record.
    Checks new image first, falls back to old image (needed for REMOVE events).
    """
    data = new_data if new_data else old_data

    # Try common PK field names in priority order
    for field in (
        'customer_id', 'user_key', 'transaction_id',
        'dispute_id', 'role_key', 'feature_key', 'license_key',
    ):
        if field in data:
            return str(data[field])

    return 'unknown'


def calculate_changes(old_data: dict, new_data: dict) -> dict:
    """
    Return a dict of {field: {old, new}} for fields that changed.
    Excludes audit timestamp fields to reduce noise.
    """
    SKIP_FIELDS = {'modified_at', 'created_at', 'modified_by'}
    changes = {}

    all_keys = set(old_data.keys()) | set(new_data.keys())
    for key in all_keys:
        if key in SKIP_FIELDS:
            continue
        old_val = old_data.get(key)
        new_val = new_data.get(key)
        if old_val != new_val:
            changes[key] = {'old': old_val, 'new': new_val}

    return changes


def convert_dynamodb_json(dynamodb_json: dict) -> dict:
    """Convert DynamoDB typed JSON format to plain Python dict."""
    if not dynamodb_json:
        return {}

    result = {}
    for key, value in dynamodb_json.items():
        if 'S' in value:
            result[key] = value['S']
        elif 'N' in value:
            result[key] = float(value['N'])
        elif 'BOOL' in value:
            result[key] = value['BOOL']
        elif 'NULL' in value:
            result[key] = None
        elif 'M' in value:
            result[key] = convert_dynamodb_json(value['M'])
        elif 'L' in value:
            result[key] = [
                convert_dynamodb_json({'v': item}).get('v', item)
                for item in value['L']
            ]
    return result


def send_cloudwatch_metrics(event_type: str, action: str, customer_id: str):
    """Fire a custom CloudWatch metric. Non-fatal if it fails."""
    try:
        cloudwatch.put_metric_data(
            Namespace='ProviderManager/Events',
            MetricData=[
                {
                    'MetricName': 'EventCount',
                    'Dimensions': [
                        {'Name': 'EventType', 'Value': event_type or 'unknown'},
                        {'Name': 'Action',    'Value': action or 'unknown'},
                    ],
                    'Value': 1,
                    'Unit': 'Count',
                    'Timestamp': datetime.utcnow()
                }
            ]
        )
    except Exception as e:
        logger.warning(f"CloudWatch metric failed (non-fatal): {str(e)}")


def trigger_webhooks(customer_id: str, event_record: dict):
    """Queue webhook deliveries for matching active webhook configs. Non-fatal."""
    try:
        queue_url = os.environ.get('WEBHOOK_QUEUE_URL')
        if not queue_url:
            return

        from boto3.dynamodb.conditions import Key, Attr
        webhooks_table = dynamodb.Table('WebhookEvent')
        response = webhooks_table.query(
            IndexName='customer_id-created_at-index',
            KeyConditionExpression=Key('customer_id').eq(customer_id),
            FilterExpression=Attr('status').eq('active')
        )

        matching = [
            w for w in response.get('Items', [])
            if event_record.get('eventType') in w.get('eventTypes', [])
        ]

        if not matching:
            return

        sqs = boto3.client('sqs')
        for webhook in matching:
            sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps({
                    'webhookId': webhook['webhook_key'],
                    'url':       webhook['url'],
                    'event':     event_record,
                    'secret':    webhook.get('secret'),
                }, default=str)
            )

        logger.info(f"Queued {len(matching)} webhook(s) for customer {customer_id}")

    except Exception as e:
        logger.warning(f"Webhook trigger failed (non-fatal): {str(e)}")
