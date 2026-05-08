# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Respond to Dispute
Submit evidence and response for a dispute
"""
import json
import boto3
import os
from utils.http_api_compat import normalize_event, get_http_method, get_path_parameter, get_query_parameter, parse_json_body
import logging
from datetime import datetime
from boto3.dynamodb.conditions import Key
from utils.cors_utils import create_response
from utils.track_api_call import tracked

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
disputes_table = dynamodb.Table('Dispute')
s3 = boto3.client('s3')

EVIDENCE_BUCKET = os.environ.get('EVIDENCE_BUCKET')

@tracked
def lambda_handler(event, context):
    """
    Respond to a dispute with evidence
    
    Expected payload:
    {
        "dispute_id": "disp_20250115120000_cust123",
        "response_message": "We have proof of delivery...",
        "evidence": {
            "description": "Delivery confirmation and customer correspondence",
            "documents": [
                {
                    "type": "delivery_confirmation",
                    "url": "s3://bucket/path/to/document.pdf",
                    "description": "Signed delivery receipt"
                },
                {
                    "type": "customer_communication",
                    "url": "s3://bucket/path/to/email.pdf",
                    "description": "Email confirmation from customer"
                }
            ]
        },
        "action": "accept|challenge"
    }
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

    logger.info(f"Respond to dispute request - ProviderId: {provider_id}, UserId: {user_id}")
    logger.info(f"Dispute {action}ed: {dispute_id} by user {user_id}")
    logger.warning(f"Dispute not found: {dispute_id} (user {user_id})")  # when not found

    try:
        # Handle OPTIONS request
        if get_http_method(event) == 'OPTIONS':
            return create_response(200, True)
        
        logger.info(f"Respond to dispute request: {json.dumps(event, default=str)}")
        
        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        # Validate required fields
        dispute_id = body.get('dispute_id')
        if not dispute_id:
            return create_response(
                400, False,
                error="dispute_id is required"
            )
        
        action = body.get('action', 'challenge')
        if action not in ['accept', 'challenge']:
            return create_response(
                400, False,
                error="action must be 'accept' or 'challenge'"
            )
        
        response_message = body.get('response_message', '')
        evidence = body.get('evidence', {})
        
        # Get dispute
        response = disputes_table.query(
            KeyConditionExpression=Key('dispute_id').eq(dispute_id)
        )
        
        items = response.get('Items', [])
        if not items:
            return create_response(
                404, False,
                error=f"Dispute not found: {dispute_id}"
            )
        
        dispute = items[0]
        
        # Validate dispute status
        if dispute['status'] not in ['open', 'under_review']:
            return create_response(
                400, False,
                error=f"Cannot respond to dispute with status: {dispute['status']}"
            )
        
        timestamp = datetime.utcnow().isoformat()
        
        # Prepare update
        update_expr_parts = []
        expr_attr_values = {}
        
        if action == 'accept':
            # Accept the dispute (don't challenge)
            update_expr_parts.append('#status = :status')
            expr_attr_values[':status'] = 'accepted'
            
            update_expr_parts.append('resolution = :resolution')
            expr_attr_values[':resolution'] = 'accepted_by_merchant'
            
            update_expr_parts.append('resolution_date = :res_date')
            expr_attr_values[':res_date'] = timestamp
        else:
            # Challenge the dispute with evidence
            update_expr_parts.append('#status = :status')
            expr_attr_values[':status'] = 'under_review'
            
            update_expr_parts.append('evidence_submitted = :evidence_flag')
            expr_attr_values[':evidence_flag'] = True
            
            if evidence:
                update_expr_parts.append('evidence = :evidence')
                expr_attr_values[':evidence'] = evidence
            
            if response_message:
                update_expr_parts.append('response_message = :message')
                expr_attr_values[':message'] = response_message
            
            update_expr_parts.append('response_submitted_at = :response_date')
            expr_attr_values[':response_date'] = timestamp
        
        # Always update timestamp
        update_expr_parts.append('updated_at = :timestamp')
        expr_attr_values[':timestamp'] = timestamp
        
        # Update dispute
        update_expression = 'SET ' + ', '.join(update_expr_parts)

        # After building update_expr_parts, add:
        update_expr_parts.append('status_updated_by = :updated_by')
        expr_attr_values[':updated_by'] = user_id
                
        updated_response = disputes_table.update_item(
            Key={'dispute_id': dispute_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues=expr_attr_values,
            ReturnValues='ALL_NEW'
        )
        
        updated_dispute = updated_response['Attributes']
        
        logger.info(f"Dispute response submitted: {dispute_id} - {action}")
        
        # Prepare response
        response_data = {
            'dispute_id': dispute_id,
            'action': action,
            'status': updated_dispute['status'],
            'evidence_submitted': updated_dispute.get('evidence_submitted', False),
            'updated_at': timestamp,
            'message': f"Dispute {action}ed successfully"
        }
        
        if action == 'accept':
            response_data['resolution'] = 'accepted_by_merchant'
            response_data['resolution_date'] = timestamp
        
        return create_response(200, True, response_data)
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return create_response(400, False, error="Invalid JSON in request body")
    
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return create_response(500, False, error=f"Failed: {str(e)}")