# VFE SaaS Framework — API Rules
<!-- CLAUDE INSTRUCTION: Apply every rule in this document when generating, modifying, or reviewing Python Lambda functions for any VFE SaaS application. -->

## Overview

All API Lambda functions in a VFE application follow the patterns established in the reference implementations: `create_user.py`, `delete_user.py`, `get_user.py`, `list_users.py`, `update_user.py`, and `update_user_status.py`. The `template.yaml` file is the reference for infrastructure definition.

---

## 1. Lambda Code Standards

### 1.1 File Naming Convention

Each Lambda is a single Python file named after its operation:

```
create_{entity}.py
get_{entity}.py
list_{entity}s.py
update_{entity}.py
update_{entity}_status.py
delete_{entity}.py
```

All files for an entity live in `src/{entity_plural}/`. For example:
```
src/users/create_user.py
src/users/get_user.py
src/users/list_users.py
src/users/update_user.py
src/users/update_user_status.py
src/users/delete_user.py
```

### 1.2 Required Imports

Every Lambda must include:

```python
import json
import boto3
import traceback
from datetime import datetime
from decimal import Decimal
```

Add as needed:
```python
import hashlib       # for password hashing
import uuid          # for GUID generation
from boto3.dynamodb.conditions import Key  # for GSI queries
```

### 1.3 Standard Helper Functions

Every Lambda file must include these three helpers by importing them from utils layer:

```python
from utils.lambda_utils import extract_user_context,decimal_default,create_response
```


every lanbda function must be decorated with:
```python
@tracked
```

This requires every lambda function includes:
```python
from track_api_call import tracked
```


### 1.4 GUID and Password Helpers (when applicable)

```python
def generate_guid():
    return str(uuid.uuid4())

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()
```

---

## 2. Lambda Handler Pattern

### 2.1 Handler Signature and Structure

```python
def lambda_handler(event, context):
    """
    <Description of operation>
    <HTTP METHOD> /<resource path>
    """
    print(f"Event: {json.dumps(event, default=decimal_default)}")
    print(f"Context: {context}")

    try:
        # 1. Handle OPTIONS preflight
        http_method = event.get('requestContext', {}).get('http', {}).get('method')
        if http_method == 'OPTIONS':
            return create_response(200, True)

        # 2. Extract user context from headers
        user_context = extract_user_context(event)

        # 3. Extract and validate path parameters
        path_params = event.get('pathParameters', {})
        # ... validate required params ...

        # 4. Parse body (for POST/PUT)
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})

        # 5. Business logic and DynamoDB operations

        # 6. Return success response
        return create_response(200, True, { ... })

    except json.JSONDecodeError as e:
        print(traceback.format_exc())
        return create_response(400, False, error="Invalid JSON in request body")
    except Exception as e:
        print(f"Error: {str(e)}")
        print(traceback.format_exc())
        return create_response(500, False, error=f"Operation failed: {str(e)}")
```

### 2.2 HTTP Status Code Conventions

| Situation | Status Code |
|---|---|
| Successful retrieval | 200 |
| Successful creation | 201 |
| OPTIONS preflight | 200 |
| Missing required field | 400 |
| Invalid input | 400 |
| Record not found | 404 |
| Server error | 500 |

### 2.3 Password Security

- Never store plaintext passwords
- Always hash with SHA-256: `hashlib.sha256(password.encode()).hexdigest()`
- Never return `password_hash` in API responses — strip it before returning:
  ```python
  user_response = {k: v for k, v in user.items() if k != 'password_hash'}
  ```

---

## 3. DynamoDB Access Patterns

### 3.1 Table Initialization

Initialize DynamoDB at module level (outside the handler) for connection reuse:

```python
dynamodb = boto3.resource('dynamodb')
USER_TABLE = dynamodb.Table('User')
```

### 3.2 Get Single Record

```python
response = TABLE.get_item(Key={'primary_key': key_value})
if 'Item' not in response:
    return create_response(404, False, error=f"Record not found: {key_value}")
item = response['Item']
```

### 3.3 Query via GSI

```python
from boto3.dynamodb.conditions import Key

response = TABLE.query(
    IndexName='gsi-index-name',
    KeyConditionExpression=Key('partition_key').eq(value)
)
items = response.get('Items', [])
```

### 3.4 Update Item

```python
response = TABLE.update_item(
    Key={'primary_key': key_value},
    UpdateExpression="SET field1 = :val1, modified_at = :modified_at, modified_by = :modified_by",
    ExpressionAttributeValues={
        ':val1': new_value,
        ':modified_at': datetime.utcnow().isoformat(),
        ':modified_by': user_context['user_id'] or 'system'
    },
    ReturnValues='ALL_NEW'
)
updated_item = response['Attributes']
```

### 3.5 Reserved Word Handling

Use `ExpressionAttributeNames` when a field name is a DynamoDB reserved word (e.g., `status`, `name`):

```python
TABLE.update_item(
    Key={'primary_key': key_value},
    UpdateExpression="SET #status = :status",
    ExpressionAttributeNames={'#status': 'status'},
    ExpressionAttributeValues={':status': new_status}
)
```

---

## 4. Standard Record Fields

Every entity record must include these audit fields:

| Field | Type | Set by |
|---|---|---|
| `created_at` | ISO 8601 string | Lambda on create |
| `modified_at` | ISO 8601 string | Lambda on every write |
| `created_by` | string | `user_context['user_id']` or `'system'` |
| `modified_by` | string | `user_context['user_id']` or `'system'` |

Set timestamps with: `datetime.utcnow().isoformat()`

---

## 5. Status Values

The `status` field on user-facing entities must use these standard values:

```
active | suspended | inactive
```

Status updates must be handled by a dedicated `update_{entity}_status.py` Lambda, not bundled into the general update Lambda.

---

## 6. CRUD Lambda Requirement

**Every DynamoDB table must have a complete set of CRUD Lambdas**, even if they are not wired to a UI in the first release. The minimum required set for each table is:

| Lambda file | HTTP method | Path pattern |
|---|---|---|
| `create_{entity}.py` | POST | `/{parents}/{entity_plural}` |
| `list_{entity}s.py` | GET | `/{parents}/{entity_plural}` |
| `get_{entity}.py` | GET | `/{parents}/{entity_plural}/{key}` |
| `update_{entity}.py` | PUT | `/{parents}/{entity_plural}/{key}` |
| `update_{entity}_status.py` | PUT | `/{parents}/{entity_plural}/{key}/status` |
| `delete_{entity}.py` | DELETE | `/{parents}/{entity_plural}/{key}` |

---

## 7. template.yaml Rules

### 7.1 SAM Transform Header

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
```

### 7.2 Global Function Defaults

```yaml
Globals:
  Function:
    Timeout: 30
    Runtime: python3.13
    Environment:
      Variables:
        CORS_ORIGIN: !Ref CorsOrigin
        ENVIRONMENT: !Ref Environment
        LOG_LEVEL: INFO
```

### 7.3 Lambda Function Definition Pattern

```yaml
Create{Entity}Function:
  Type: AWS::Serverless::Function
  Properties:
    FunctionName: "create-{entity}"
    CodeUri: src/{entity_plural}/
    Handler: create_{entity}.lambda_handler
    Layers:
      - !Ref UtilsLayer
    Policies:
      - DynamoDBCrudPolicy:
          TableName: !Ref {Entity}Table
    Environment:
      Variables:
        {ENTITY}_TABLE: !Ref {Entity}Table
    Events:
      HttpApi:
        Type: HttpApi
        Properties:
          ApiId: !Ref ProviderManagerHttpApi
          Path: /{parents}/{entity_plural}
          Method: POST
```

### 7.4 Policy Conventions

| Operation | Policy |
|---|---|
| Read-only Lambda | `DynamoDBReadPolicy` |
| Write Lambda (create/update/delete) | `DynamoDBCrudPolicy` |
| Multiple tables | Add one policy block per table |

### 7.5 Shared API Gateway

All Lambdas attach to the **single shared** API Gateway:

```yaml
ApiId: !Ref ProviderManagerHttpApi
```

Never create a new `AWS::Serverless::HttpApi` resource for new entities — always reference the existing one.

### 7.6 Layer Attachment

Attach `UtilsLayer` to all Lambdas. Attach `JWTLayer` only to auth Lambdas:

```yaml
Layers:
  - !Ref UtilsLayer         # always
  - !Ref JWTLayer            # auth Lambdas only
```

---

## 8. Reference Files

When generating new Lambdas, mirror the exact patterns in these reference files:

| Reference file | Demonstrates |
|---|---|
| `create_user.py` | POST with validation, email uniqueness check, GUID generation, password hashing |
| `get_user.py` | GET single record by primary key, 404 handling |
| `list_users.py` | GET list via GSI query, sort, strip sensitive fields |
| `update_user.py` | PUT with selective field updates, password rehash if supplied |
| `update_user_status.py` | PUT status-only update, reserved word handling, valid status list |
| `delete_user.py` | DELETE with existence check, return deleted record |
