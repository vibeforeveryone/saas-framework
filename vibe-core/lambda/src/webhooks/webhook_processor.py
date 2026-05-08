# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Webhook Processor
Processes queued webhooks and updates transaction records
Supports AWS API Gateway V2 with header-based authentication
"""
import json
import boto3
import traceback
from datetime import datetime
from decimal import Decimal
from boto3.dynamodb.conditions import Key
from utils.track_api_call import tracked
from utils.lambda_utils import extract_user_context,decimal_default,create_response


dynamodb = boto3.resource('dynamodb')
WEBHOOKS_TABLE = dynamodb.Table('WebhookEvent')
TRANSACTIONS_TABLE = dynamodb.Table('PaymentTransaction')



def process_merchantone_webhook(payload):
    """Process MerchantOne webhook payload"""
    event_type = payload.get('event_type')
    transaction_data = payload.get('transaction', {})
    
    return {
        'event_type': event_type,
        'processor_transaction_id': transaction_data.get('transaction_id'),
        'status': transaction_data.get('status'),
        'amount': Decimal(str(transaction_data.get('amount', 0))),
        'metadata': transaction_data
    }

def process_paysafe_webhook(payload):
    """Process PaySafe webhook payload"""
    event_type = payload.get('eventType')
    data = payload.get('data', {})
    
    amount = Decimal(str(data.get('amount', 0))) / Decimal('100')
    
    return {
        'event_type': event_type,
        'processor_transaction_id': data.get('id'),
        'status': data.get('status'),
        'amount': amount,
        'metadata': data
    }

def process_paymentnerds_webhook(payload):
    """Process PaymentNerds webhook payload"""
    event_type = payload.get('transaction_type')
    status = 'completed' if payload.get('response') == '1' else 'failed'
    
    return {
        'event_type': event_type,
        'processor_transaction_id': payload.get('transactionid'),
        'status': status,
        'amount': Decimal(str(payload.get('amount', 0))),
        'metadata': payload
    }

def find_transaction_by_processor_id(processor_transaction_id):
    """Find transaction by processor transaction ID using GSI"""
    try:
        response = TRANSACTIONS_TABLE.query(
            IndexName='transaction_key-index',
            KeyConditionExpression=Key('transaction_key').eq(processor_transaction_id),
            Limit=1
        )
        
        items = response.get('Items', [])
        return items[0] if items else None
        
    except Exception as e:
        print(f"Error finding transaction: {str(e)}")
        print(traceback.format_exc())
        return None

def update_transaction_status(transaction_id, webhook_data):
    """Update transaction based on webhook data"""
    try:
        timestamp = datetime.utcnow().isoformat()
        
        update_expression = "SET #status = :status, updated_at = :timestamp, webhook_updated = :flag"
        expression_values = {
            ':status': webhook_data['status'],
            ':timestamp': timestamp,
            ':flag': True
        }
        
        if webhook_data.get('metadata'):
            update_expression += ", webhook_data = :metadata"
            expression_values[':metadata'] = webhook_data['metadata']
        
        TRANSACTIONS_TABLE.update_item(
            Key={'transaction_id': transaction_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues=expression_values
        )
        
        print(f"Transaction updated: {transaction_id} -> {webhook_data.get('status')}")
        return True
        
    except Exception as e:
        print(f"Error updating transaction: {str(e)}")
        print(traceback.format_exc())
        return False

@tracked
def lambda_handler(event, context):
    """
    Process webhook from SQS queue
    Triggered by SQS messages
    """
    print(f"Event: {json.dumps(event, default=decimal_default)}")
    print(f"Context: {context}")
    
    try:
        records = event.get('Records', [])
        print(f"Processing {len(records)} webhook messages")
        
        processed = 0
        failed = 0
        
        for record in records:
            try:
                message = json.loads(record['body'])
                webhook_id = message['webhook_id']
                processor_type = message['processor_type']
                
                print(f"Processing webhook: {webhook_id}")
                
                # Get webhook from DynamoDB
                response = WEBHOOKS_TABLE.get_item(Key={'webhook_key': webhook_id})
                
                if 'Item' not in response:
                    print(f"Webhook not found: {webhook_id}")
                    failed += 1
                    continue
                
                webhook = response['Item']
                payload = webhook['payload']
                
                # Process based on processor type
                webhook_data = None
                
                if processor_type == 'merchantone':
                    webhook_data = process_merchantone_webhook(payload)
                elif processor_type == 'paysafe':
                    webhook_data = process_paysafe_webhook(payload)
                elif processor_type == 'paymentnerds':
                    webhook_data = process_paymentnerds_webhook(payload)
                else:
                    print(f"Unknown processor type: {processor_type}")
                    failed += 1
                    continue
                
                processor_transaction_id = webhook_data.get('processor_transaction_id')
                
                if not processor_transaction_id:
                    print(f"No processor transaction ID in webhook: {webhook_id}")
                    WEBHOOKS_TABLE.update_item(
                        Key={'webhook_key': webhook_id},
                        UpdateExpression='SET #status = :status, processed_at = :timestamp',
                        ExpressionAttributeNames={'#status': 'status'},
                        ExpressionAttributeValues={
                            ':status': 'processed_no_action',
                            ':timestamp': datetime.utcnow().isoformat()
                        }
                    )
                    processed += 1
                    continue
                
                transaction = find_transaction_by_processor_id(processor_transaction_id)
                
                if not transaction:
                    print(f"Transaction not found for processor ID: {processor_transaction_id}")
                    WEBHOOKS_TABLE.update_item(
                        Key={'webhook_key': webhook_id},
                        UpdateExpression='SET #status = :status, processed_at = :timestamp',
                        ExpressionAttributeNames={'#status': 'status'},
                        ExpressionAttributeValues={
                            ':status': 'processed_not_found',
                            ':timestamp': datetime.utcnow().isoformat()
                        }
                    )
                    processed += 1
                    continue
                
                # Update transaction
                success = update_transaction_status(transaction['transaction_id'], webhook_data)
                
                if success:
                    WEBHOOKS_TABLE.update_item(
                        Key={'webhook_key': webhook_id},
                        UpdateExpression='SET #status = :status, processed_at = :timestamp',
                        ExpressionAttributeNames={'#status': 'status'},
                        ExpressionAttributeValues={
                            ':status': 'processed',
                            ':timestamp': datetime.utcnow().isoformat()
                        }
                    )
                    processed += 1
                else:
                    WEBHOOKS_TABLE.update_item(
                        Key={'webhook_key': webhook_id},
                        UpdateExpression='SET #status = :status, retry_count = retry_count + :inc',
                        ExpressionAttributeNames={'#status': 'status'},
                        ExpressionAttributeValues={
                            ':status': 'failed',
                            ':inc': 1
                        }
                    )
                    failed += 1
                
            except Exception as e:
                print(f"Error processing webhook record: {str(e)}")
                print(traceback.format_exc())
                failed += 1
        
        print(f"Processing complete: {processed} processed, {failed} failed")
        
        return {
            'statusCode': 200,
            'body': json.dumps({'processed': processed, 'failed': failed})
        }
        
    except Exception as e:
        print(f"Error in webhook processor: {str(e)}")
        print(traceback.format_exc())
        raise
