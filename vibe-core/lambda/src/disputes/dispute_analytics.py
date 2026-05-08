# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Dispute Analytics
Generate analytics and reports on dispute data
"""
import json
import boto3
import os
from utils.http_api_compat import normalize_event, get_http_method, get_path_parameter, get_query_parameter, parse_json_body
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from boto3.dynamodb.conditions import Key, Attr
from utils.cors_utils import create_response
from utils.track_api_call import tracked

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
disputes_table = dynamodb.Table('Dispute')

@tracked
def lambda_handler(event, context):
    """
    Get dispute analytics
    
    Query parameters:
    - company_name: Company to analyze (required)
    - start_date: Start date (ISO format, default: 90 days ago)
    - end_date: End date (ISO format, default: now)
    """
    # Normalize event for HTTP API compatibility
    event = normalize_event(event)
    
    
    # Extract provider_id and user_id from headers (V2 best practice)
    headers = event.get('headers', {})
    provider_id = (headers.get('X-Provider-Id') or headers.get('x-provider-id') or 
                headers.get('providerId') or 'demo-provider')
    user_id = (headers.get('X-User-Id') or headers.get('x-user-id') or 
            headers.get('userId') or 'demo-user')

    # Fallback to authorizer claims if available
    claims = event.get('requestContext', {}).get('authorizer', {}).get('claims', {})
    if provider_id == 'demo-provider':
        provider_id = claims.get('custom:providerId', provider_id)
        user_id = claims.get('sub', user_id)


    logger.info(f"Dispute analytics request - ProviderId: {provider_id}, UserId: {user_id}")
    logger.info(f"Querying disputes for {company_name} from {start_date} to {end_date}")
    logger.info(f"Analytics generated for {company_name}: {total_disputes} disputes by user {user_id}")
    
    try:
        # Handle OPTIONS request
        if get_http_method(event) == 'OPTIONS':
            return create_response(200, True)
        
        logger.info(f"Dispute analytics request: {json.dumps(event, default=str)}")
        
        # Get query parameters
        query_params = event.get('queryStringParameters') or {}
        
        company_name = query_params.get('company_name')
        if not company_name:
            return create_response(
                400, False,
                error="company_name query parameter is required"
            )
        
        # Date range (default: last 90 days)
        end_date = query_params.get('end_date', datetime.utcnow().isoformat())
        start_date = query_params.get(
            'start_date',
            (datetime.utcnow() - timedelta(days=90)).isoformat()
        )
        
        # Query disputes in date range
        logger.info(f"Querying disputes for {company_name} from {start_date} to {end_date}")
        
        response = disputes_table.query(
            IndexName='CustomerIndex',
            KeyConditionExpression=Key('company_name').eq(company_name),
            FilterExpression=Attr('created_at').between(start_date, end_date)
        )
        
        items = response.get('Items', [])
        
        # Initialize analytics
        analytics = {
            'company_name': company_name,
            'period': {
                'start_date': start_date,
                'end_date': end_date
            },
            'overview': {},
            'by_status': {},
            'by_type': {},
            'by_reason': {},
            'win_loss_ratio': {},
            'financial_impact': {},
            'timeline': []
        }
        
        if not items:
            analytics['overview'] = {
                'total_disputes': 0,
                'message': 'No disputes found in this period'
            }
            return create_response(200, True, analytics)
        
        # Calculate overview
        total_disputes = len(items)
        total_disputed_amount = sum(float(i['disputed_amount']) for i in items)
        
        open_disputes = [i for i in items if i['status'] == 'open']
        under_review = [i for i in items if i['status'] == 'under_review']
        won_disputes = [i for i in items if i['status'] == 'won']
        lost_disputes = [i for i in items if i['status'] == 'lost']
        closed_disputes = [i for i in items if i['status'] == 'closed']
        
        analytics['overview'] = {
            'total_disputes': total_disputes,
            'total_disputed_amount': round(total_disputed_amount, 2),
            'open': len(open_disputes),
            'under_review': len(under_review),
            'won': len(won_disputes),
            'lost': len(lost_disputes),
            'closed': len(closed_disputes),
            'currency': items[0]['currency'] if items else 'USD'
        }
        
        # Calculate win rate
        resolved = len(won_disputes) + len(lost_disputes)
        if resolved > 0:
            win_rate = len(won_disputes) / resolved * 100
            analytics['win_loss_ratio'] = {
                'won': len(won_disputes),
                'lost': len(lost_disputes),
                'win_rate': round(win_rate, 2),
                'total_resolved': resolved
            }
        
        # Group by status
        status_stats = defaultdict(lambda: {'count': 0, 'amount': 0})
        for item in items:
            status = item['status']
            status_stats[status]['count'] += 1
            status_stats[status]['amount'] += float(item['disputed_amount'])
        
        analytics['by_status'] = {
            status: {
                'count': data['count'],
                'amount': round(data['amount'], 2),
                'percentage': round(data['count'] / total_disputes * 100, 2)
            }
            for status, data in status_stats.items()
        }
        
        # Group by type
        type_stats = defaultdict(lambda: {'count': 0, 'amount': 0})
        for item in items:
            dispute_type = item['dispute_type']
            type_stats[dispute_type]['count'] += 1
            type_stats[dispute_type]['amount'] += float(item['disputed_amount'])
        
        analytics['by_type'] = {
            dtype: {
                'count': data['count'],
                'amount': round(data['amount'], 2)
            }
            for dtype, data in type_stats.items()
        }
        
        # Group by reason code
        reason_stats = defaultdict(int)
        for item in items:
            reason = item.get('reason_code', 'unknown')
            reason_stats[reason] += 1
        
        analytics['by_reason'] = dict(reason_stats)
        
        # Financial impact
        amount_lost = sum(
            float(i.get('final_amount', i['disputed_amount']))
            for i in lost_disputes
        )
        
        amount_recovered = sum(
            float(i['disputed_amount']) - float(i.get('final_amount', 0))
            for i in won_disputes
        )
        
        analytics['financial_impact'] = {
            'total_at_risk': round(total_disputed_amount, 2),
            'amount_lost': round(amount_lost, 2),
            'amount_recovered': round(amount_recovered, 2),
            'net_impact': round(amount_lost, 2)
        }
        
        # Timeline analysis (by month)
        timeline_data = defaultdict(lambda: {'count': 0, 'amount': 0, 'won': 0, 'lost': 0})
        
        for item in items:
            month_key = item['created_at'][:7]  # YYYY-MM
            timeline_data[month_key]['count'] += 1
            timeline_data[month_key]['amount'] += float(item['disputed_amount'])
            
            if item['status'] == 'won':
                timeline_data[month_key]['won'] += 1
            elif item['status'] == 'lost':
                timeline_data[month_key]['lost'] += 1
        
        analytics['timeline'] = [
            {
                'month': month,
                'count': data['count'],
                'amount': round(data['amount'], 2),
                'won': data['won'],
                'lost': data['lost']
            }
            for month, data in sorted(timeline_data.items())
        ]
        
        # Top customers by disputes
        customer_stats = defaultdict(lambda: {'count': 0, 'amount': 0, 'email': '', 'name': ''})
        
        for item in items:
            cust_id = item['customer_id']
            customer_stats[cust_id]['count'] += 1
            customer_stats[cust_id]['amount'] += float(item['disputed_amount'])
            customer_stats[cust_id]['email'] = item.get('customer_email', '')
            customer_stats[cust_id]['name'] = item.get('customer_name', '')
        
        # Sort by count and take top 10
        top_customers = sorted(
            [
                {
                    'customer_id': cust_id,
                    'customer_name': data['name'],
                    'customer_email': data['email'],
                    'dispute_count': data['count'],
                    'total_disputed_amount': round(data['amount'], 2)
                }
                for cust_id, data in customer_stats.items()
            ],
            key=lambda x: x['dispute_count'],
            reverse=True
        )[:10]
        
        analytics['top_customers'] = top_customers
        
        logger.info(f"Analytics generated for {company_name}: {total_disputes} disputes")
        
        return create_response(200, True, analytics)
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return create_response(500, False, error=f"Failed: {str(e)}")