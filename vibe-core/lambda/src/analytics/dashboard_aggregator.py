# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Dashboard Aggregator
Aggregates real metrics from source tables and returns them in the flat
shape that DashboardHome.js expects:

{
  total_transactions:         int,
  total_revenue:              float,
  active_disputes:            int,
  total_customers:            int,
  active_subscriptions:       int,
  monthly_recurring_revenue:  float,
  recent_activity:            list[event]   (last 10 EventsLog records)
}

GET  /dashboard/metrics          — returns metrics for the caller's customer_id
POST /dashboard/metrics/refresh  — same, forces a fresh calculation
"""
import json
import boto3
import traceback
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr
from utils.track_api_call import tracked
from utils.lambda_utils import extract_user_context, decimal_default, create_response

dynamodb = boto3.resource('dynamodb')

EVENTS_LOG_TABLE        = dynamodb.Table('EventsLog')
PAYMENT_TRANSACTION_TABLE = dynamodb.Table('PaymentTransaction')
CUSTOMERS_TABLE         = dynamodb.Table('Customers')
DISPUTE_TABLE           = dynamodb.Table('Dispute')
CUSTOMER_LICENSE_TABLE  = dynamodb.Table('CustomerLicenseHistory')


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

@tracked
def lambda_handler(event, context):
    print(f"Event: {json.dumps(event, default=decimal_default)}")

    try:
        http_method = event.get('requestContext', {}).get('http', {}).get('method')
        if http_method == 'OPTIONS':
            return create_response(200, True)

        user_context = extract_user_context(event)
        print(f"User context: {json.dumps(user_context)}")

        query_params = event.get('queryStringParameters') or {}
        customer_id  = query_params.get('customer_id') or user_context.get('customer_id')

        if not customer_id:
            return create_response(400, False, error="Missing customer_id")

        is_super_user = user_context.get('is_super_user', False)

        if is_super_user:
            data = aggregate_platform_metrics()
        else:
            data = aggregate_customer_metrics(customer_id)

        return create_response(200, True, data)

    except Exception as e:
        print(f"Error aggregating dashboard: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to aggregate dashboard: {str(e)}")


# ---------------------------------------------------------------------------
# Customer-scoped metrics (regular admin user)
# ---------------------------------------------------------------------------

def aggregate_customer_metrics(customer_id: str) -> dict:
    """
    Aggregate metrics for a single customer.
    Runs four parallel-style queries (DynamoDB does not support true parallel
    queries in Python without threading, so we run them sequentially — each
    is a single indexed query, not a scan, so latency is low).
    """
    total_transactions = 0
    total_revenue      = 0.0
    active_disputes    = 0
    active_subscriptions      = 0
    monthly_recurring_revenue = 0.0

    # ── 1. Transactions ───────────────────────────────────────────────
    try:
        response = PAYMENT_TRANSACTION_TABLE.query(
            IndexName='customer_id-created_at-index',
            KeyConditionExpression=Key('customer_id').eq(customer_id),
            ProjectionExpression='transaction_id, amount, #s',
            ExpressionAttributeNames={'#s': 'status'},
        )
        items = response.get('Items', [])

        # Handle pagination (customers with many transactions)
        while 'LastEvaluatedKey' in response:
            response = PAYMENT_TRANSACTION_TABLE.query(
                IndexName='customer_id-created_at-index',
                KeyConditionExpression=Key('customer_id').eq(customer_id),
                ProjectionExpression='transaction_id, amount, #s',
                ExpressionAttributeNames={'#s': 'status'},
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            items.extend(response.get('Items', []))

        total_transactions = len(items)
        total_revenue = sum(
            float(item.get('amount', 0))
            for item in items
            if item.get('status') == 'completed'
        )
    except Exception as e:
        print(f"Error querying transactions: {str(e)}")

    # ── 2. Active disputes ────────────────────────────────────────────
    try:
        dispute_response = DISPUTE_TABLE.query(
            IndexName='CustomerIndex',
            KeyConditionExpression=Key('customer_id').eq(customer_id),
            FilterExpression=Attr('status').is_in(
                ['open', 'pending', 'under_review']
            ),
            Select='COUNT'
        )
        active_disputes = dispute_response.get('Count', 0)
    except Exception as e:
        print(f"Error querying disputes: {str(e)}")

    # ── 3. Active license / subscriptions ─────────────────────────────
    try:
        license_response = CUSTOMER_LICENSE_TABLE.query(
            KeyConditionExpression=Key('customer_id').eq(customer_id),
            FilterExpression=Attr('end_date').eq('active'),
        )
        active_items = license_response.get('Items', [])
        active_subscriptions = len(active_items)
        monthly_recurring_revenue = sum(
            float(item.get('monthly_cost', 0)) for item in active_items
        )
    except Exception as e:
        print(f"Error querying licenses: {str(e)}")

    # ── 4. Recent activity from EventsLog ─────────────────────────────
    recent_activity = []
    try:
        activity_response = EVENTS_LOG_TABLE.query(
            KeyConditionExpression=Key('customer_id').eq(customer_id),
            ScanIndexForward=False,   # most recent first
            Limit=10,
        )
        recent_activity = activity_response.get('Items', [])
    except Exception as e:
        print(f"Error querying recent activity: {str(e)}")

    return {
        'total_transactions':        total_transactions,
        'total_revenue':             round(total_revenue, 2),
        'active_disputes':           active_disputes,
        'total_customers':           1,       # scoped to this customer
        'active_subscriptions':      active_subscriptions,
        'monthly_recurring_revenue': round(monthly_recurring_revenue, 2),
        'recent_activity':           recent_activity,
    }


# ---------------------------------------------------------------------------
# Platform-wide metrics (superuser)
# ---------------------------------------------------------------------------

def aggregate_platform_metrics() -> dict:
    """
    Aggregate metrics across the entire platform for superuser dashboard view.
    Uses table scans — acceptable because this is a privileged, low-frequency call.
    For high-volume deployments consider a scheduled aggregation job instead.
    """
    total_transactions = 0
    total_revenue      = 0.0
    active_disputes    = 0
    total_customers    = 0
    active_subscriptions      = 0
    monthly_recurring_revenue = 0.0

    # ── 1. Total customers ────────────────────────────────────────────
    try:
        response = CUSTOMERS_TABLE.scan(Select='COUNT')
        total_customers = response.get('Count', 0)
        while 'LastEvaluatedKey' in response:
            response = CUSTOMERS_TABLE.scan(
                Select='COUNT',
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            total_customers += response.get('Count', 0)
    except Exception as e:
        print(f"Error counting customers: {str(e)}")

    # ── 2. All transactions ───────────────────────────────────────────
    try:
        response = PAYMENT_TRANSACTION_TABLE.scan(
            ProjectionExpression='transaction_id, amount, #s',
            ExpressionAttributeNames={'#s': 'status'}
        )
        items = response.get('Items', [])
        while 'LastEvaluatedKey' in response:
            response = PAYMENT_TRANSACTION_TABLE.scan(
                ProjectionExpression='transaction_id, amount, #s',
                ExpressionAttributeNames={'#s': 'status'},
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            items.extend(response.get('Items', []))

        total_transactions = len(items)
        total_revenue = sum(
            float(item.get('amount', 0))
            for item in items
            if item.get('status') == 'completed'
        )
    except Exception as e:
        print(f"Error scanning transactions: {str(e)}")

    # ── 3. Active disputes ────────────────────────────────────────────
    try:
        response = DISPUTE_TABLE.scan(
            FilterExpression=Attr('status').is_in(['open', 'pending', 'under_review']),
            Select='COUNT'
        )
        active_disputes = response.get('Count', 0)
        while 'LastEvaluatedKey' in response:
            response = DISPUTE_TABLE.scan(
                FilterExpression=Attr('status').is_in(
                    ['open', 'pending', 'under_review']),
                Select='COUNT',
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            active_disputes += response.get('Count', 0)
    except Exception as e:
        print(f"Error scanning disputes: {str(e)}")

    # ── 4. Active subscriptions / MRR ────────────────────────────────
    try:
        response = CUSTOMER_LICENSE_TABLE.scan(
            FilterExpression=Attr('end_date').eq('active')
        )
        active_items = response.get('Items', [])
        while 'LastEvaluatedKey' in response:
            response = CUSTOMER_LICENSE_TABLE.scan(
                FilterExpression=Attr('end_date').eq('active'),
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            active_items.extend(response.get('Items', []))

        active_subscriptions      = len(active_items)
        monthly_recurring_revenue = sum(
            float(item.get('monthly_cost', 0)) for item in active_items
        )
    except Exception as e:
        print(f"Error scanning licenses: {str(e)}")

    # ── 5. Recent platform-wide activity (last 10 across all customers) ─
    # EventsLog is keyed on customer_id — a cross-customer "latest 10"
    # would require a full scan. We return empty here and let the
    # analytics screen serve that use case for superusers.
    recent_activity = []

    return {
        'total_transactions':        total_transactions,
        'total_revenue':             round(total_revenue, 2),
        'active_disputes':           active_disputes,
        'total_customers':           total_customers,
        'active_subscriptions':      active_subscriptions,
        'monthly_recurring_revenue': round(monthly_recurring_revenue, 2),
        'recent_activity':           recent_activity,
    }
