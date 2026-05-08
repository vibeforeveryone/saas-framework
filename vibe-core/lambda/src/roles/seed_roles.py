# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Seed Roles
CloudFormation Custom Resource Lambda.
On stack Create/Update: ensures the two default system roles exist.
On stack Delete: does nothing (DeletionPolicy: Retain protects the table).

These records are system-wide and created once — not per customer.
"""
import json
import boto3
import traceback
import uuid
import urllib.request
from datetime import datetime
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
ROLE_TABLE = dynamodb.Table('Role')

DEFAULT_ROLES = [
    {'role_desc': 'Admin',     'is_default': True},
    {'role_desc': 'Invoicing', 'is_default': False},
]


def send_cfn_response(event, context, status, reason="", data=None):
    """Send result back to CloudFormation via pre-signed S3 URL."""
    body = json.dumps({
        'Status': status,
        'Reason': reason,
        'PhysicalResourceId': event.get('PhysicalResourceId', context.log_stream_name),
        'StackId': event['StackId'],
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'],
        'Data': data or {}
    }).encode('utf-8')

    url = event['ResponseURL']
    req = urllib.request.Request(
        url,
        data=body,
        headers={'Content-Type': '', 'Content-Length': len(body)},
        method='PUT'
    )
    urllib.request.urlopen(req)


def seed_roles():
    """
    For each default role, check if a record with that role_desc already exists.
    If not, create it. Idempotent — safe to run on every Update.
    """
    created = []
    skipped = []

    for role_def in DEFAULT_ROLES:
        # Check via GSI
        response = ROLE_TABLE.query(
            IndexName='role_desc-index',
            KeyConditionExpression=Key('role_desc').eq(role_def['role_desc'])
        )

        if response.get('Items'):
            skipped.append(role_def['role_desc'])
            print(f"Role already exists, skipping: {role_def['role_desc']}")
            continue

        role_key = str(uuid.uuid4())
        current_time = datetime.utcnow().isoformat()

        role = {
            'role_key': role_key,
            'role_desc': role_def['role_desc'],
            'is_default': role_def['is_default'],
            'created_at': current_time,
            'modified_at': current_time,
            'created_by': 'system_seed',
            'modified_by': 'system_seed',
        }

        ROLE_TABLE.put_item(Item=role)
        created.append(role_def['role_desc'])
        print(f"Seeded role: {role_def['role_desc']} ({role_key})")

    return created, skipped


def lambda_handler(event, context):
    print(f"Event: {json.dumps(event)}")

    request_type = event.get('RequestType', 'Create')

    try:
        if request_type == 'Delete':
            # Never delete seed data — table has DeletionPolicy: Retain anyway
            send_cfn_response(event, context, 'SUCCESS', reason="Delete is a no-op for seed data")
            return

        # Create or Update — both are idempotent
        created, skipped = seed_roles()

        send_cfn_response(event, context, 'SUCCESS',
            reason=f"Seeded {len(created)} role(s). Skipped {len(skipped)} existing.",
            data={'created': created, 'skipped': skipped}
        )

    except Exception as e:
        print(f"Error in seed_roles: {str(e)}")
        print(traceback.format_exc())
        send_cfn_response(event, context, 'FAILED', reason=str(e))
