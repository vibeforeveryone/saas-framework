# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
Update Dispute Status
Update dispute status (typically from processor webhook or manual review)
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

@tracked
def lambda_handler(event, context):
    """
    Update dispute status
    
    Expected payload:
    {
        "dispute_id": "disp_20250115120000_cust123",
        "status": "won|lost|closed",
        "resolution": "merchant_won|customer_won|withdrawn|etc",
        "resolution_notes": "Customer withdrew dispute",
        "final_amount": 0.00  // Amount lost/refunded
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

    logger.info(f"Update dispute status request - ProviderId: {provider_id}, UserId: {user_id}")
    logger.info(f"Dispute status updated: {dispute_id} - {current_status} -> {new_status} by user {user_id} (provider: {provider_id})")

    try:
        # Handle OPTIONS request
        if get_http_method(event) == 'OPTIONS':
            return create_response(200, True)
        
        logger.info(f"Update dispute status request: {json.dumps(event, default=str)}")
        
        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        # Validate required fields
        dispute_id = body.get('dispute_id')
        new_status = body.get('status')
        
        if not dispute_id:
            return create_response(
                400, False,
                error="dispute_id is required"
            )
        
        if not new_status:
            return create_response(
                400, False,
                error="status is required"
            )
        
        valid_statuses = ['open', 'under_review', 'won', 'lost', 'closed', 'accepted']
        if new_status not in valid_statuses:
            return create_response(
                400, False,
                error=f"status must be one of: {', '.join(valid_statuses)}"
            )
        
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
        current_status = dispute['status']
        
        timestamp = datetime.utcnow().isoformat()
        
        # Prepare update
        update_expr_parts = []
        expr_attr_values = {}
        
        update_expr_parts.append('#status = :status')
        expr_attr_values[':status'] = new_status
        
        update_expr_parts.append('updated_at = :timestamp')
        expr_attr_values[':timestamp'] = timestamp
        
        # Add resolution if status is final
        if new_status in ['won', 'lost', 'closed']:
            resolution = body.get('resolution')
            if resolution:
                update_expr_parts.append('resolution = :resolution')
                expr_attr_values[':resolution'] = resolution
            
            update_expr_parts.append('resolution_date = :res_date')
            expr_attr_values[':res_date'] = timestamp
            
            resolution_notes = body.get('resolution_notes')
            if resolution_notes:
                update_expr_parts.append('resolution_notes = :notes')
                expr_attr_values[':notes'] = resolution_notes
            
            final_amount = body.get('final_amount')
            if final_amount is not None:
                from decimal import Decimal
                update_expr_parts.append('final_amount = :final_amt')
                expr_attr_values[':final_amt'] = Decimal(str(final_amount))
        
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
        
        logger.info(f"Dispute status updated: {dispute_id} - {current_status} -> {new_status}")
        
        # Prepare response
        response_data = {
            'dispute_id': dispute_id,
            'previous_status': current_status,
            'current_status': new_status,
            'updated_at': timestamp
        }
        
        if updated_dispute.get('resolution'):
            response_data['resolution'] = updated_dispute['resolution']
            response_data['resolution_date'] = updated_dispute.get('resolution_date')
        
        if updated_dispute.get('final_amount'):
            response_data['final_amount'] = float(updated_dispute['final_amount'])
        
        return create_response(200, True, response_data)
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return create_response(400, False, error="Invalid JSON in request body")
    
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return create_response(500, False, error=f"Failed: {str(e)}")