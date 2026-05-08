# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Seed Licenses
CloudFormation Custom Resource Lambda.
On stack Create/Update: ensures the system-wide license tiers exist.
On stack Delete: does nothing (DeletionPolicy: Retain protects the table).

Idempotent — checks for an existing record with the same license_type +
tier_desc before writing, so re-running on Update is safe.

Two license types:
  maxseats            — flat monthly fee based on seat count
  transactionspermonth — usage-based, billed per transaction
"""
import json
import boto3
import traceback
import uuid
import urllib.request
from datetime import datetime
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr

dynamodb    = boto3.resource('dynamodb')
LICENSE_TABLE = dynamodb.Table('License')

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------
# maxseats tiers
# Fields: tier_desc, min_users, max_users, monthly_cost, discount_percentage,
#         license_type, is_active
MAXSEATS_TIERS = [
    {
        'tier_desc':            'Up to 5 Seats',
        'min_users':            1,
        'max_users':            5,
        'monthly_cost':         Decimal('10.00'),
        'discount_percentage':  Decimal('0'),
        'license_type':         'maxseats',
        'is_active':            True,
    },
    {
        'tier_desc':            'Up to 10 Seats',
        'min_users':            6,
        'max_users':            10,
        'monthly_cost':         Decimal('18.00'),
        'discount_percentage':  Decimal('0'),
        'license_type':         'maxseats',
        'is_active':            True,
    },
    {
        'tier_desc':            'Up to 25 Seats',
        'min_users':            11,
        'max_users':            25,
        'monthly_cost':         Decimal('40.00'),
        'discount_percentage':  Decimal('0'),
        'license_type':         'maxseats',
        'is_active':            True,
    },
    {
        'tier_desc':            'Up to 100 Seats',
        'min_users':            26,
        'max_users':            100,
        'monthly_cost':         Decimal('150.00'),
        'discount_percentage':  Decimal('0'),
        'license_type':         'maxseats',
        'is_active':            True,
    },
    {
        'tier_desc':            'Up to 250 Seats',
        'min_users':            101,
        'max_users':            250,
        'monthly_cost':         Decimal('250.00'),
        'discount_percentage':  Decimal('0'),
        'license_type':         'maxseats',
        'is_active':            True,
    },
    {
        'tier_desc':            'Up to 1000 Seats',
        'min_users':            251,
        'max_users':            1000,
        'monthly_cost':         Decimal('400.00'),
        'discount_percentage':  Decimal('0'),
        'license_type':         'maxseats',
        'is_active':            True,
    },
    {
        'tier_desc':            'Unlimited Seats',
        'min_users':            1001,
        'max_users':            100000,
        'monthly_cost':         Decimal('10000.00'),
        'discount_percentage':  Decimal('0'),
        'license_type':         'maxseats',
        'is_active':            True,
    },
]

TRANSACTIONS_TIERS = [
    {
        'tier_desc':                'Transactions Per Month',
        'min_users':                0,
        'max_users':                0,          # not applicable for this type
        'monthly_cost':             Decimal('3.00'),
        'cost_per_transaction':     Decimal('0.003'),
        'discount_percentage':      Decimal('0'),
        'license_type':             'transactionspermonth',
        'is_active':                True,
    },
]

ALL_SEED_TIERS = MAXSEATS_TIERS + TRANSACTIONS_TIERS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def send_cfn_response(event, context, status, reason='', data=None):
    """Send result back to CloudFormation via pre-signed S3 URL."""
    body = json.dumps({
        'Status':             status,
        'Reason':             reason,
        'PhysicalResourceId': event.get('PhysicalResourceId',
                                        context.log_stream_name),
        'StackId':            event['StackId'],
        'RequestId':          event['RequestId'],
        'LogicalResourceId':  event['LogicalResourceId'],
        'Data':               data or {},
    }).encode('utf-8')

    req = urllib.request.Request(
        event['ResponseURL'],
        data=body,
        headers={'Content-Type': '', 'Content-Length': len(body)},
        method='PUT'
    )
    urllib.request.urlopen(req)


def tier_already_exists(tier_desc, license_type):
    """
    Check whether a record with this exact tier_desc + license_type
    already exists anywhere in the table (scan with filter — table is tiny).
    Returns True if found, False otherwise.
    """
    response = LICENSE_TABLE.scan(
        FilterExpression=(
            Attr('tier_desc').eq(tier_desc) &
            Attr('license_type').eq(license_type)
        )
    )
    return len(response.get('Items', [])) > 0


def seed_licenses():
    """
    For each seed tier, check if a matching record already exists.
    If not, create it. Idempotent — safe on every stack Update.
    Returns (created_list, skipped_list).
    """
    created = []
    skipped = []
    current_time = datetime.utcnow().isoformat()

    for tier in ALL_SEED_TIERS:
        if tier_already_exists(tier['tier_desc'], tier['license_type']):
            skipped.append(tier['tier_desc'])
            print(f"License already exists, skipping: {tier['tier_desc']}")
            continue

        record = {
            'license_key':  str(uuid.uuid4()),
            'created_at':   current_time,
            'modified_at':  current_time,
            'created_by':   'system_seed',
            'modified_by':  'system_seed',
            **tier,                         # spread all tier fields
        }

        LICENSE_TABLE.put_item(Item=record)
        created.append(tier['tier_desc'])
        print(f"Seeded license: {tier['tier_desc']} "
              f"(type={tier['license_type']}, "
              f"cost=${tier['monthly_cost']})")

    return created, skipped


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

def lambda_handler(event, context):
    print(f"Event: {json.dumps(event)}")

    request_type = event.get('RequestType', 'Create')

    try:
        if request_type == 'Delete':
            # Never delete seed data — table has DeletionPolicy: Retain anyway
            send_cfn_response(event, context, 'SUCCESS',
                              reason='Delete is a no-op for seed data')
            return

        # Create or Update — both are idempotent
        created, skipped = seed_licenses()

        send_cfn_response(
            event, context, 'SUCCESS',
            reason=f"Seeded {len(created)} tier(s). Skipped {len(skipped)} existing.",
            data={'created': created, 'skipped': skipped}
        )

    except Exception as e:
        print(f"Error in seed_licenses: {str(e)}")
        print(traceback.format_exc())
        send_cfn_response(event, context, 'FAILED', reason=str(e))
