# VFE SaaS Framework — Database
<!-- CLAUDE INSTRUCTION: Apply every rule in this document when generating or modifying DynamoDB table definitions in template.yaml for any VFE SaaS application. -->

## Overview

All VFE SaaS applications use **AWS DynamoDB** as the data layer. Every table is defined in `template.yaml` as an `AWS::DynamoDB::Table` resource. This document defines the conventions, required settings, and complete table catalogue for the VFE framework.

---

## 1. Global Table Conventions

### 1.1 Required Settings for Every Table

```yaml
BillingMode: PAY_PER_REQUEST      # Always — never PROVISIONED
```

### 1.2 Required Settings for Sensitive / Core Tables

```yaml
PointInTimeRecoverySpecification:
  PointInTimeRecoveryEnabled: true

SSESpecification:
  SSEEnabled: true
```

Apply to: `User`, `Customers`, `EmailVerificationCodes`, and any table storing PII or credentials.

### 1.3 DynamoDB Streams (Event-Driven Tables)

```yaml
StreamSpecification:
  StreamViewType: NEW_AND_OLD_IMAGES
```

Apply to: `User`, `Application`, `Role`, `PaymentTransaction`, `WebhookEvent`, `EventsLog`.

### 1.4 TTL (Time-to-Live)

```yaml
TimeToLiveSpecification:
  AttributeName: ttl
  Enabled: true
```

Apply to: `EmailVerificationCodes`, `DashboardMetrics`, `EventsLog`.

### 1.5 Tagging

```yaml
Tags:
  - Key: Application
    Value: ProviderManager
  - Key: Environment
    Value: !Ref Environment
```

### 1.6 Primary Key Naming Convention

- Primary key field names end in `_key` (GUID) or `_id` (natural/composite identifier)
- Range keys are used where natural sort order is needed (e.g., `timestamp`, `app_key`, `seq`)

---

## 2. Attribute Types

DynamoDB only indexes declared attributes. Only attributes used in KeySchema or GSI KeySchema are declared in `AttributeDefinitions`.

| Suffix / Pattern | DynamoDB Type |
|---|---|
| `_key`, `_id`, `_name`, `_email`, `_desc`, `_status`, `customer_id`, etc. | `S` (String) |
| `seq`, numeric counters | `N` (Number) |

---

## 3. Global Secondary Index (GSI) Conventions

- GSI names follow the pattern: `{hash_field}-{range_field}-index`
- All GSIs use `ProjectionType: ALL`
- Design GSIs for the most common query patterns (e.g., list by parent, lookup by email)

```yaml
GlobalSecondaryIndexes:
  - IndexName: customer_id-user_name-index
    KeySchema:
      - AttributeName: customer_id
        KeyType: HASH
      - AttributeName: user_name
        KeyType: RANGE
    Projection:
      ProjectionType: ALL
```

---

## 4. Complete Table Catalogue

### 4.1 Core Identity Tables

#### Customers
```yaml
CustomersTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: Customers
    BillingMode: PAY_PER_REQUEST
    AttributeDefinitions:
      - { AttributeName: customer_id, AttributeType: S }
      - { AttributeName: company_name, AttributeType: S }
      - { AttributeName: email, AttributeType: S }
    KeySchema:
      - { AttributeName: customer_id, KeyType: HASH }
    GlobalSecondaryIndexes:
      - IndexName: CustomerIndex
        KeySchema:
          - { AttributeName: company_name, KeyType: HASH }
          - { AttributeName: customer_id, KeyType: RANGE }
        Projection: { ProjectionType: ALL }
      - IndexName: EmailIndex
        KeySchema:
          - { AttributeName: email, KeyType: HASH }
        Projection: { ProjectionType: ALL }
    PointInTimeRecoverySpecification: { PointInTimeRecoveryEnabled: true }
    SSESpecification: { SSEEnabled: true }
```

**Attributes:** `customer_id` (HASH), `company_name`, `email`, `status`, `created_at`, `modified_at`, `created_by`, `modified_by`

---

#### User
```yaml
UserTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: "User"
    BillingMode: PAY_PER_REQUEST
    AttributeDefinitions:
      - { AttributeName: user_key, AttributeType: S }
      - { AttributeName: customer_id, AttributeType: S }
      - { AttributeName: user_name, AttributeType: S }
      - { AttributeName: user_email, AttributeType: S }
    KeySchema:
      - { AttributeName: user_key, KeyType: HASH }
    GlobalSecondaryIndexes:
      - IndexName: customer_id-user_name-index
        KeySchema:
          - { AttributeName: customer_id, KeyType: HASH }
          - { AttributeName: user_name, KeyType: RANGE }
        Projection: { ProjectionType: ALL }
      - IndexName: user_email-index
        KeySchema:
          - { AttributeName: user_email, KeyType: HASH }
        Projection: { ProjectionType: ALL }
    StreamSpecification: { StreamViewType: NEW_AND_OLD_IMAGES }
```

**Attributes:** `user_key` (HASH), `customer_id`, `user_name`, `user_email`, `password_hash`, `status` (`active`/`suspended`/`inactive`), `is_super_user`, `created_at`, `modified_at`, `created_by`, `modified_by`


---

### 4.2 Application Configuration Tables

#### Application
```yaml
ApplicationTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: "Application"
    BillingMode: PAY_PER_REQUEST
    AttributeDefinitions:
      - { AttributeName: app_key, AttributeType: S }
    KeySchema:
      - { AttributeName: app_key, KeyType: HASH }
    StreamSpecification: { StreamViewType: NEW_AND_OLD_IMAGES }
    PointInTimeRecoverySpecification: { PointInTimeRecoveryEnabled: true }
    SSESpecification: { SSEEnabled: true }
```

**Attributes:** `app_key` (HASH), `app_name`, `app_desc`, `status`, `created_at`, `modified_at`

---

#### Role
```yaml
RoleTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: "Role"
    BillingMode: PAY_PER_REQUEST
    AttributeDefinitions:
      - { AttributeName: role_key, AttributeType: S }
      - { AttributeName: app_key, AttributeType: S }
      - { AttributeName: role_desc, AttributeType: S }
    KeySchema:
      - { AttributeName: role_key, KeyType: HASH }
    GlobalSecondaryIndexes:
      - IndexName: app_key-role_desc-index
        KeySchema:
          - { AttributeName: app_key, KeyType: HASH }
          - { AttributeName: role_desc, KeyType: RANGE }
        Projection: { ProjectionType: ALL }
    StreamSpecification: { StreamViewType: NEW_AND_OLD_IMAGES }
```

**Attributes:** `role_key` (HASH), `app_key`, `role_desc`, `created_at`, `modified_at`

---

#### Feature
```yaml
FeatureTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: "Feature"
    BillingMode: PAY_PER_REQUEST
    AttributeDefinitions:
      - { AttributeName: feature_key, AttributeType: S }
      - { AttributeName: app_key, AttributeType: S }
      - { AttributeName: feature_desc, AttributeType: S }
    KeySchema:
      - { AttributeName: feature_key, KeyType: HASH }
    GlobalSecondaryIndexes:
      - IndexName: app_key-feature_desc-index
        KeySchema:
          - { AttributeName: app_key, KeyType: HASH }
          - { AttributeName: feature_desc, KeyType: RANGE }
        Projection: { ProjectionType: ALL }
```

**Attributes:** `feature_key` (HASH), `app_key`, `feature_desc`, `created_at`, `modified_at`

---

#### License
```yaml
LicenseTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: "License"
    BillingMode: PAY_PER_REQUEST
    AttributeDefinitions:
      - { AttributeName: license_key, AttributeType: S }
      - { AttributeName: app_key, AttributeType: S }
      - { AttributeName: tier_desc, AttributeType: S }
    KeySchema:
      - { AttributeName: license_key, KeyType: HASH }
    GlobalSecondaryIndexes:
      - IndexName: app_key-tier_desc-index
        KeySchema:
          - { AttributeName: app_key, KeyType: HASH }
          - { AttributeName: tier_desc, KeyType: RANGE }
        Projection: { ProjectionType: ALL }
```

**Attributes:** `license_key` (HASH), `app_key`, `tier_desc`, `max_users`, `price`, `billing_period`, `created_at`, `modified_at`

---

### 4.3 Pricing Tables

#### FlatBaseRate
```yaml
FlatBaseRateTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: "FlatBaseRate"
    BillingMode: PAY_PER_REQUEST
    AttributeDefinitions:
      - { AttributeName: app_key, AttributeType: S }
    KeySchema:
      - { AttributeName: app_key, KeyType: HASH }
```

**Attributes:** `app_key` (HASH), `base_rate`, `currency`, `modified_at`

---

#### APIRate
```yaml
APIRateTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: "APIRate"
    BillingMode: PAY_PER_REQUEST
    AttributeDefinitions:
      - { AttributeName: app_key, AttributeType: S }
      - { AttributeName: seq, AttributeType: N }
    KeySchema:
      - { AttributeName: app_key, KeyType: HASH }
      - { AttributeName: seq, KeyType: RANGE }
```

**Attributes:** `app_key` (HASH), `seq` (RANGE), `tier_name`, `from_calls`, `to_calls`, `rate_per_call`

---

### 4.4 Customer-Application Association Tables

#### CustomerApplicationLicense
```yaml
CustomerApplicationLicenseTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: "CustomerApplicationLicense"
    BillingMode: PAY_PER_REQUEST
    AttributeDefinitions:
      - { AttributeName: customer_id, AttributeType: S }
      - { AttributeName: app_key, AttributeType: S }
    KeySchema:
      - { AttributeName: customer_id, KeyType: HASH }
      - { AttributeName: app_key, KeyType: RANGE }
```

**Attributes:** `customer_id` (HASH), `app_key` (RANGE), `license_key`, `status`, `start_date`, `end_date`, `created_at`, `modified_at`

---

#### UserAppRole
```yaml
UserAppRoleTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: "UserAppRole"
    BillingMode: PAY_PER_REQUEST
    AttributeDefinitions:
      - { AttributeName: user_key, AttributeType: S }
      - { AttributeName: app_key, AttributeType: S }
    KeySchema:
      - { AttributeName: user_key, KeyType: HASH }
      - { AttributeName: app_key, KeyType: RANGE }
```

**Attributes:** `user_key` (HASH), `app_key` (RANGE), `role_key`, `assigned_at`, `created_at`, `modified_at`, `created_by`, `modified_by`

---

#### UserAppFeature

> Note: `app_feature_key` is a composite key formatted as `{app_key}#{feature_key}`

```yaml
UserAppFeatureTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: "UserAppFeature"
    BillingMode: PAY_PER_REQUEST
    AttributeDefinitions:
      - { AttributeName: user_key, AttributeType: S }
      - { AttributeName: app_feature_key, AttributeType: S }
    KeySchema:
      - { AttributeName: user_key, KeyType: HASH }
      - { AttributeName: app_feature_key, KeyType: RANGE }
```

**Attributes:** `user_key` (HASH), `app_feature_key` (RANGE), `app_key`, `feature_key`, `assigned_at`, `created_at`, `modified_at`

---

### 4.5 Payment Tables

#### PaymentProcessorConfig
```yaml
PaymentProcessorConfigTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: "PaymentProcessorConfig"
    BillingMode: PAY_PER_REQUEST
    AttributeDefinitions:
      - { AttributeName: customer_id, AttributeType: S }
      - { AttributeName: processor_name, AttributeType: S }
    KeySchema:
      - { AttributeName: customer_id, KeyType: HASH }
      - { AttributeName: processor_name, KeyType: RANGE }
```

**Attributes:** `customer_id` (HASH), `processor_name` (RANGE), `api_key`, `api_secret`, `is_active`, `environment`, `created_at`, `modified_at`

---

#### PaymentTransaction
```yaml
PaymentTransactionTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: "PaymentTransaction"
    BillingMode: PAY_PER_REQUEST
    AttributeDefinitions:
      - { AttributeName: transaction_id, AttributeType: S }
      - { AttributeName: customer_id, AttributeType: S }
      - { AttributeName: created_at, AttributeType: S }
      - { AttributeName: transaction_key, AttributeType: S }
      - { AttributeName: status, AttributeType: S }
    KeySchema:
      - { AttributeName: transaction_id, KeyType: HASH }
    GlobalSecondaryIndexes:
      - IndexName: customer_id-created_at-index
        KeySchema: [{ AttributeName: customer_id, KeyType: HASH }, { AttributeName: created_at, KeyType: RANGE }]
        Projection: { ProjectionType: ALL }
      - IndexName: transaction_key-index
        KeySchema: [{ AttributeName: transaction_key, KeyType: HASH }]
        Projection: { ProjectionType: ALL }
      - IndexName: status-created_at-index
        KeySchema: [{ AttributeName: status, KeyType: HASH }, { AttributeName: created_at, KeyType: RANGE }]
        Projection: { ProjectionType: ALL }
    StreamSpecification: { StreamViewType: NEW_AND_OLD_IMAGES }
```

---

#### Dispute
```yaml
DisputeTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: "Dispute"
    BillingMode: PAY_PER_REQUEST
    AttributeDefinitions:
      - { AttributeName: dispute_id, AttributeType: S }
      - { AttributeName: transaction_id, AttributeType: S }
      - { AttributeName: status, AttributeType: S }
      - { AttributeName: created_at, AttributeType: S }
    KeySchema:
      - { AttributeName: dispute_id, KeyType: HASH }
    GlobalSecondaryIndexes:
      - IndexName: transaction_id-index
        KeySchema: [{ AttributeName: transaction_id, KeyType: HASH }]
        Projection: { ProjectionType: ALL }
      - IndexName: status-created_at-index
        KeySchema: [{ AttributeName: status, KeyType: HASH }, { AttributeName: created_at, KeyType: RANGE }]
        Projection: { ProjectionType: ALL }
```

---

### 4.6 System / Event Tables

#### UsageTable
```yaml
UsageTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: UsageTable
    BillingMode: PAY_PER_REQUEST
    AttributeDefinitions:
      - { AttributeName: user_name, AttributeType: S }
      - { AttributeName: timestamp, AttributeType: S }
      - { AttributeName: company_name, AttributeType: S }
      - { AttributeName: app_name, AttributeType: S }
    KeySchema:
      - { AttributeName: user_name, KeyType: HASH }
      - { AttributeName: timestamp, KeyType: RANGE }
    GlobalSecondaryIndexes:
      - IndexName: CustomerIndex
        KeySchema: [{ AttributeName: company_name, KeyType: HASH }, { AttributeName: timestamp, KeyType: RANGE }]
        Projection: { ProjectionType: ALL }
      - IndexName: AppIndex
        KeySchema: [{ AttributeName: app_name, KeyType: HASH }, { AttributeName: timestamp, KeyType: RANGE }]
        Projection: { ProjectionType: ALL }
```

---

#### WebhookEvent
```yaml
WebhookEventTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: "WebhookEvent"
    BillingMode: PAY_PER_REQUEST
    AttributeDefinitions:
      - { AttributeName: webhook_key, AttributeType: S }
      - { AttributeName: customer_id, AttributeType: S }
      - { AttributeName: created_at, AttributeType: S }
      - { AttributeName: status, AttributeType: S }
    KeySchema:
      - { AttributeName: webhook_key, KeyType: HASH }
    GlobalSecondaryIndexes:
      - IndexName: customer_id-created_at-index
        KeySchema: [{ AttributeName: customer_id, KeyType: HASH }, { AttributeName: created_at, KeyType: RANGE }]
        Projection: { ProjectionType: ALL }
      - IndexName: status-created_at-index
        KeySchema: [{ AttributeName: status, KeyType: HASH }, { AttributeName: created_at, KeyType: RANGE }]
        Projection: { ProjectionType: ALL }
    StreamSpecification: { StreamViewType: NEW_AND_OLD_IMAGES }
```

---

#### Notification
```yaml
NotificationTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: "Notification"
    BillingMode: PAY_PER_REQUEST
    AttributeDefinitions:
      - { AttributeName: notification_id, AttributeType: S }
      - { AttributeName: user_key, AttributeType: S }
      - { AttributeName: created_at, AttributeType: S }
    KeySchema:
      - { AttributeName: notification_id, KeyType: HASH }
    GlobalSecondaryIndexes:
      - IndexName: user_key-created_at-index
        KeySchema: [{ AttributeName: user_key, KeyType: HASH }, { AttributeName: created_at, KeyType: RANGE }]
        Projection: { ProjectionType: ALL }
```

---

#### EmailVerificationCodes
```yaml
EmailVerificationCodesTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: EmailVerificationCodes
    BillingMode: PAY_PER_REQUEST
    AttributeDefinitions:
      - { AttributeName: code_id, AttributeType: S }
      - { AttributeName: email, AttributeType: S }
      - { AttributeName: timestamp, AttributeType: S }
    KeySchema:
      - { AttributeName: code_id, KeyType: HASH }
    GlobalSecondaryIndexes:
      - IndexName: email-timestamp-index
        KeySchema: [{ AttributeName: email, KeyType: HASH }, { AttributeName: timestamp, KeyType: RANGE }]
        Projection: { ProjectionType: ALL }
    TimeToLiveSpecification: { AttributeName: ttl, Enabled: true }
    PointInTimeRecoverySpecification: { PointInTimeRecoveryEnabled: true }
    SSESpecification: { SSEEnabled: true }
```

---

#### EventsLog
```yaml
EventsLogTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: "EventsLog"
    BillingMode: PAY_PER_REQUEST
    AttributeDefinitions:
      - { AttributeName: customer_id, AttributeType: S }
      - { AttributeName: timestamp, AttributeType: S }
      - { AttributeName: eventType, AttributeType: S }
      - { AttributeName: userId, AttributeType: S }
    KeySchema:
      - { AttributeName: customer_id, KeyType: HASH }
      - { AttributeName: timestamp, KeyType: RANGE }
    GlobalSecondaryIndexes:
      - IndexName: eventType-timestamp-index
        KeySchema: [{ AttributeName: eventType, KeyType: HASH }, { AttributeName: timestamp, KeyType: RANGE }]
        Projection: { ProjectionType: ALL }
      - IndexName: userId-timestamp-index
        KeySchema: [{ AttributeName: userId, KeyType: HASH }, { AttributeName: timestamp, KeyType: RANGE }]
        Projection: { ProjectionType: ALL }
    StreamSpecification: { StreamViewType: NEW_AND_OLD_IMAGES }
    TimeToLiveSpecification: { AttributeName: ttl, Enabled: true }
```

---

### 4.7 Analytics Tables

#### Reports
Primary key: `customer_id` (HASH) + `reportId` (RANGE). GSI on `reportId` and `customer_id-createdAt`.

#### DashboardMetrics
Primary key: `customer_id` (HASH) + `metricDate` (RANGE). TTL enabled.

#### ExportJobs
Primary key: `customer_id` (HASH) + `jobId` (RANGE). GSI on `customer_id-createdAt`.

#### KpiMetrics
Primary key: `metricName` (HASH) + `timestamp` (RANGE). GSI on `customer_id-timestamp`.

#### ScheduledReports
Primary key: `customer_id` (HASH) + `scheduleId` (RANGE).

#### UsageMetrics
Primary key: `customer_id` (HASH) + `metricDate` (RANGE). GSI on `appKey-metricDate`.

---

## 5. Adding a New Table (Checklist)

When adding a new DynamoDB table to a VFE application:

1. Define the table in `template.yaml` following the conventions in section 1
2. Choose a GUID-based `_key` primary key (or a natural composite key if appropriate)
3. Add GSIs for every expected query pattern
4. Enable SSE and PITR for tables containing PII
5. Enable TTL for ephemeral data tables
6. Enable Streams if the table needs to trigger downstream processing
7. Add the table reference to the environment variables of all Lambdas that access it
8. Add `DynamoDBCrudPolicy` or `DynamoDBReadPolicy` to each Lambda's `Policies` section
9. Create a complete set of CRUD Lambdas (see `VFE_SaaS_framework_API_rules.md` section 6)
