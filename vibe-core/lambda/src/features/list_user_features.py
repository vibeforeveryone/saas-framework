# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
List User Features
Returns all features assigned to a user, including feature_desc names.
GET /customers/{customer_id}/users/{user_key}/features
"""
import json
import boto3
import traceback
from boto3.dynamodb.conditions import Key
from utils.track_api_call import tracked
from utils.lambda_utils import extract_user_context, decimal_default, create_response

dynamodb = boto3.resource('dynamodb')
USER_FEATURE_TABLE = dynamodb.Table('UserFeature')
FEATURE_TABLE = dynamodb.Table('Feature')


@tracked
def lambda_handler(event, context):
    print(f"Event: {json.dumps(event, default=decimal_default)}")

    try:
        http_method = event.get('requestContext', {}).get('http', {}).get('method')
        if http_method == 'OPTIONS':
            return create_response(200, True)

        user_context = extract_user_context(event)
        print(f"User context: {json.dumps(user_context)}")

        path_params = event.get('pathParameters', {})
        user_key = path_params.get('user_key')

        if not user_key:
            return create_response(400, False, error="Missing user_key in path")

        response = USER_FEATURE_TABLE.query(
            KeyConditionExpression=Key('user_key').eq(user_key)
        )
        assignments = response.get('Items', [])

        if not assignments:
            return create_response(200, True, {'features': [], 'count': 0})

        # Batch-fetch feature details
        feature_keys = [{'feature_key': a['feature_key']} for a in assignments]

        batch_response = dynamodb.batch_get_item(
            RequestItems={
                'Feature': {
                    'Keys': feature_keys,
                    'ProjectionExpression': 'feature_key, feature_desc'
                }
            }
        )

        feature_map = {
            f['feature_key']: f
            for f in batch_response.get('Responses', {}).get('Feature', [])
        }

        enriched = []
        for assignment in assignments:
            fk = assignment['feature_key']
            feature_detail = feature_map.get(fk, {})
            enriched.append({
                'feature_key': fk,
                'feature_desc': feature_detail.get('feature_desc', ''),
                'assigned_at': assignment.get('assigned_at', ''),
                'assigned_by': assignment.get('assigned_by', ''),
                'customer_id': assignment.get('customer_id', ''),
            })

        enriched = sorted(enriched, key=lambda x: x.get('feature_desc', '').lower())

        print(f"Retrieved {len(enriched)} feature assignments for user {user_key}")

        return create_response(200, True, {
            'features': enriched,
            'count': len(enriched)
        })

    except Exception as e:
        print(f"Error listing user features: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to list user features: {str(e)}")
