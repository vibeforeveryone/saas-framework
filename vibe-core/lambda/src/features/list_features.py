# Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
# Author: Christopher Niven
"""
List Features
Returns all system-wide features. No app_key filter.
GET /features
"""
import json
import boto3
import traceback
from utils.track_api_call import tracked
from utils.lambda_utils import extract_user_context, decimal_default, create_response

dynamodb = boto3.resource('dynamodb')
FEATURE_TABLE = dynamodb.Table('Feature')


@tracked
def lambda_handler(event, context):
    print(f"Event: {json.dumps(event)}")

    try:
        http_method = event.get('requestContext', {}).get('http', {}).get('method')
        if http_method == 'OPTIONS':
            return create_response(200, True)

        user_context = extract_user_context(event)
        print(f"User context: {json.dumps(user_context)}")

        response = FEATURE_TABLE.scan()
        features = response.get('Items', [])

        while 'LastEvaluatedKey' in response:
            response = FEATURE_TABLE.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            features.extend(response.get('Items', []))

        features = sorted(features, key=lambda x: x.get('feature_desc', '').lower())

        print(f"Retrieved {len(features)} system features")

        return create_response(200, True, {
            'features': features,
            'count': len(features)
        })

    except Exception as e:
        print(f"Error listing features: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Failed to list features: {str(e)}")
