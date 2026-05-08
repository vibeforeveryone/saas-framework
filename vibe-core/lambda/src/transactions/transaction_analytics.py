# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Transaction Analytics
Generate analytics and reports on transaction data
"""
import json
import boto3
import os
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from collections import defaultdict
from boto3.dynamodb.conditions import Key, Attr
from cors_utils import create_response
from utils.track_api_call import tracked
from utils.lambda_utils import extract_user_context,decimal_default,create_response


logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
transactions_table = dynamodb.Table('TransactionsTable')

@tracked
def lambda_handler(event, context):
    """
    Get transaction analytics
    
    Query parameters:
    - company_name: Company to analyze (required)
    - start_date: Start date (ISO format, default: 30 days ago)
    - end_date: End date (ISO format, default: now)
    - group_by: Group results by (day, week, month, processor, status)
    """
    try:
        # Handle OPTIONS request
        if event.get('httpMethod') == 'OPTIONS':
            return create_response(200, True)
        
        logger.info(f"Transaction analytics request: {json.dumps(event, default=str)}")
        
        # Get query parameters
        query_params = event.get('queryStringParameters') or {}
        
        company_name = query_params.get('company_name')
        if not company_name:
            return create_response(
                400, False,
                error="company_name query parameter is required"
            )
        
        # Date range (default: last 30 days)
        end_date = query_params.get('end_date', datetime.utcnow().isoformat())
        start_date = query_params.get(
            'start_date',
            (datetime.utcnow() - timedelta(days=30)).isoformat()
        )
        
        group_by = query_params.get('group_by', 'day')
        
        # Query transactions in date range
        logger.info(f"Querying transactions for {company_name} from {start_date} to {end_date}")
        
        response = transactions_table.query(
            IndexName='CustomerIndex',
            KeyConditionExpression=Key('company_name').eq(company_name),
            FilterExpression=Attr('created_at').between(start_date, end_date)
        )
        
        items = response.get('Items', [])
        
        # Initialize analytics data
        analytics = {
            'company_name': company_name,
            'period': {
                'start_date': start_date,
                'end_date': end_date
            },
            'overview': {},
            'by_status': {},
            'by_processor': {},
            'by_type': {},
            'timeline': [],
            'top_customers': []
        }
        
        # Calculate overview metrics
        total_transactions = len(items)
        total_volume = sum(float(item['amount']) for item in items)
        
        payments = [i for i in items if i['transaction_type'] == 'payment']
        refunds = [i for i in items if i['transaction_type'] == 'refund']
        
        successful_payments = [p for p in payments if p['status'] == 'completed']
        failed_payments = [p for p in payments if p['status'] == 'failed']
        
        analytics['overview'] = {
            'total_transactions': total_transactions,
            'total_volume': round(total_volume, 2),
            'currency': items[0]['currency'] if items else 'USD',
            'total_payments': len(payments),
            'total_refunds': len(refunds),
            'successful_payments': len(successful_payments),
            'failed_payments': len(failed_payments),
            'success_rate': round(
                len(successful_payments) / len(payments) * 100, 2
            ) if payments else 0,
            'average_transaction_value': round(
                total_volume / total_transactions, 2
            ) if total_transactions > 0 else 0,
            'refund_rate': round(
                len(refunds) / len(payments) * 100, 2
            ) if payments else 0
        }
        
        # Group by status
        status_stats = defaultdict(lambda: {'count': 0, 'volume': 0})
        for item in items:
            status = item['status']
            status_stats[status]['count'] += 1
            status_stats[status]['volume'] += float(item['amount'])
        
        analytics['by_status'] = {
            status: {
                'count': data['count'],
                'volume': round(data['volume'], 2),
                'percentage': round(data['count'] / total_transactions * 100, 2)
            }
            for status, data in status_stats.items()
        }
        
        # Group by processor
        processor_stats = defaultdict(lambda: {'count': 0, 'volume': 0, 'successful': 0, 'failed': 0})
        for item in items:
            proc = item.get('processor_type', 'unknown')
            processor_stats[proc]['count'] += 1
            processor_stats[proc]['volume'] += float(item['amount'])
            
            if item['status'] == 'completed':
                processor_stats[proc]['successful'] += 1
            elif item['status'] == 'failed':
                processor_stats[proc]['failed'] += 1
        
        analytics['by_processor'] = {
            proc: {
                'count': data['count'],
                'volume': round(data['volume'], 2),
                'successful': data['successful'],
                'failed': data['failed'],
                'success_rate': round(
                    data['successful'] / data['count'] * 100, 2
                ) if data['count'] > 0 else 0
            }
            for proc, data in processor_stats.items()
        }
        
        # Group by transaction type
        type_stats = defaultdict(lambda: {'count': 0, 'volume': 0})
        for item in items:
            trans_type = item['transaction_type']
            type_stats[trans_type]['count'] += 1
            type_stats[trans_type]['volume'] += float(item['amount'])
        
        analytics['by_type'] = {
            trans_type: {
                'count': data['count'],
                'volume': round(data['volume'], 2)
            }
            for trans_type, data in type_stats.items()
        }
        
        # Timeline analysis
        if group_by == 'day':
            timeline_data = defaultdict(lambda: {'count': 0, 'volume': 0, 'successful': 0})
            
            for item in items:
                date_key = item['created_at'][:10]  # YYYY-MM-DD
                timeline_data[date_key]['count'] += 1
                timeline_data[date_key]['volume'] += float(item['amount'])
                
                if item['status'] == 'completed':
                    timeline_data[date_key]['successful'] += 1
            
            analytics['timeline'] = [
                {
                    'date': date,
                    'count': data['count'],
                    'volume': round(data['volume'], 2),
                    'successful': data['successful']
                }
                for date, data in sorted(timeline_data.items())
            ]
        
        # Top customers by volume
        customer_stats = defaultdict(lambda: {'count': 0, 'volume': 0, 'email': '', 'name': ''})
        
        for item in items:
            if item['transaction_type'] == 'payment' and item['status'] == 'completed':
                cust_id = item['customer_id']
                customer_stats[cust_id]['count'] += 1
                customer_stats[cust_id]['volume'] += float(item['amount'])
                customer_stats[cust_id]['email'] = item.get('customer_email', '')
                customer_stats[cust_id]['name'] = item.get('customer_name', '')
        
        # Sort by volume and take top 10
        top_customers = sorted(
            [
                {
                    'customer_id': cust_id,
                    'customer_name': data['name'],
                    'customer_email': data['email'],
                    'transaction_count': data['count'],
                    'total_volume': round(data['volume'], 2)
                }
                for cust_id, data in customer_stats.items()
            ],
            key=lambda x: x['total_volume'],
            reverse=True
        )[:10]
        
        analytics['top_customers'] = top_customers
        
        # Payment method breakdown
        payment_method_stats = defaultdict(int)
        for item in payments:
            method = item.get('payment_method_type', 'unknown')
            payment_method_stats[method] += 1
        
        analytics['payment_methods'] = dict(payment_method_stats)
        
        logger.info(f"Analytics generated for {company_name}: {total_transactions} transactions")
        
        return create_response(200, True, analytics)
        
    except Exception as e:
        logger.error(f"Error generating analytics: {str(e)}", exc_info=True)
        return create_response(500, False, error=f"Failed to generate analytics: {str(e)}")
