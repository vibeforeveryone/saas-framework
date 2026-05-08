# VFE SaaS Framework — Architecture
<!-- CLAUDE INSTRUCTION: This document defines the required architecture for all VibeForEveryone (VFE) SaaS applications. Follow all rules in this file and its companion documents when generating or modifying application code. -->

## Overview

The **VibeForEveryone (VFE) SaaS Framework** provides a standardized, repeatable architecture and pre-built functionality (sign-up, login, usage tracking, licensing, billing, etc.) for building SaaS applications on AWS.

All VFE applications follow a strict **n-tier architecture** with three independently hosted layers:

```
┌──────────────────────────────────────────────┐
│               Frontend Layer                 │
│       React · AWS Amplify (amplifyapp.com)   │
├──────────────────────────────────────────────┤
│                 API Layer                    │
│   Python 3.13 Lambdas · AWS API Gateway V2   │
├──────────────────────────────────────────────┤
│                Data Layer                    │
│       AWS DynamoDB · defined in template.yaml│
└──────────────────────────────────────────────┘
```

---

## Layer 1 — Frontend (React / Amplify)

- **Language:** JavaScript (React)
- **Hosting:** AWS Amplify — deployed to `*.amplifyapp.com`
- **Deployment:** Amplify Console connected to the application's Git repository
- **Key Framework Files (do not replace — only extend):**

| File | Purpose |
|---|---|
| `App.js` | Root application shell with left-side navigation and `ProtectedRoute` wrapper |
| `Navigation.js` | Left-side collapsible navigation component |
| `LoginScreen.js` | Authentication screen |
| `design-system.css` | Global VFE design tokens and component styles |
| `Navigation.css` | Navigation-specific styles |
| `config.js` | **All API calls must use this file** — centralised base URL and request helpers (`api.getWithLog`, `api.postWithLog`) |

- **Rules:** See `VFE_SaaS_framework_front_end_rules.md`

---

## Layer 2 — API Layer (Python Lambda / API Gateway)

- **Language:** Python 3.13
- **Hosting:** AWS Lambda via AWS API Gateway V2 (HTTP API)
- **Gateway resource name:** `ProviderManagerHttpApi`, stage `v1`
- **Pattern:** One Lambda function per operation (not monolithic handlers)
- **CRUD Requirement:** Complete Create, Read (get + list), Update, Delete, and status-update Lambdas **must be generated for every DynamoDB table**, even if not used in release 1
- **Shared Layers:**
  - `UtilsLayer` — common utilities, attached to most Lambdas
  - `JWTLayer` — PyJWT, attached to auth Lambdas
- **Infrastructure:** All Lambdas and the API Gateway are declared in `template.yaml`
- **Rules:** See `VFE_SaaS_framework_API_rules.md`

---

## Layer 3 — Data Layer (DynamoDB)

- **Database:** AWS DynamoDB (serverless, on-demand billing)
- **Definition:** Every table is defined in `template.yaml` as `AWS::DynamoDB::Table`
- **Billing Mode:** `PAY_PER_REQUEST` on all tables
- **Security:** `SSEEnabled: true` and `PointInTimeRecoveryEnabled: true` on sensitive tables
- **Streams:** `StreamViewType: NEW_AND_OLD_IMAGES` on tables requiring downstream triggers
- **Rules:** See `VFE_SaaS_framework_database.md`

---

## AWS Infrastructure Summary

| Component | AWS Service | Notes |
|---|---|---|
| Frontend hosting | AWS Amplify | Git-connected CI/CD |
| API Gateway | AWS API Gateway V2 (HTTP API) | Single shared `ProviderManagerHttpApi`, stage `v1` |
| Lambda runtime | AWS Lambda | Python 3.13, 30s default timeout |
| Database | AWS DynamoDB | PAY_PER_REQUEST, SSE enabled |
| File storage | AWS S3 | Reports bucket, AES256, 90-day lifecycle |
| Email | AWS SES | Verification emails and signup confirmations |
| Secrets | AWS Secrets Manager | JWT secrets and sensitive config |

---

## Source Folder Structure

```
project-root/
├── src/
│   ├── applications/        # Application CRUD Lambdas
│   ├── auth/                # Authentication Lambda
│   ├── customers/           # Customer CRUD Lambdas
│   ├── users/               # User CRUD Lambdas
│   ├── roles/               # Role CRUD Lambdas
│   ├── features/            # Feature CRUD Lambdas
│   ├── licenses/            # License CRUD Lambdas
│   ├── subscriptions/       # Subscription CRUD Lambdas
│   ├── transactions/        # Payment transaction Lambdas
│   ├── disputes/            # Dispute management Lambdas
│   ├── payment_processors/  # Processor config Lambdas
│   ├── notifications/       # Notification Lambdas
│   ├── webhooks/            # Webhook handler Lambdas
│   ├── analytics/           # Reporting and analytics Lambdas
│   ├── usage/               # Usage tracking Lambdas
│   ├── user_assignments/    # UserAppRole / UserAppFeature Lambdas
│   ├── api_rates/           # API rate config Lambdas
│   └── public/              # Unauthenticated public endpoints (signup, verify)
├── layers/
│   ├── jwt/                 # PyJWT layer
│   └── utils/               # Shared utility layer
├── frontend/src/
│   ├── App.js               # Root shell — extend, do not replace
│   ├── components/          # React components
│   └── api/config.js        # API config — ALL api calls use this
└── template.yaml            # SAM template — all infrastructure defined here
```

---

## Public vs. Protected Endpoints

| Route prefix | Auth required | Notes |
|---|---|---|
| `/public/*` | No | Sign-up, email verification, payment verification |
| All other routes | Yes | Header-based: `X-User-Id`, `X-Provider-Id`, `X-Customer-Id` |

---

## SaaS Platform Core Features (Built into Every VFE Application)

- Multi-tenant customer and user management
- Application, role, feature, and license definition
- Customer application subscriptions
- Public self-service sign-up with email verification and payment
- Usage tracking and analytics
- Payment processing, transactions, refunds, and voids
- Dispute management
- Webhook event handling (per processor)
- Notification system
- Dashboard metrics and KPI reporting
- Scheduled and custom report generation
- Data export to S3

---

## Companion Documents

| Document | Purpose |
|---|---|
| `VFE_SaaS_framework_API_rules.md` | Lambda code standards, response format, CORS, folder layout |
| `VFE_SaaS_framework_front_end_rules.md` | React component standards, routing, API access, navigation |
| `VFE_SaaS_framework_database.md` | DynamoDB table definitions, key patterns, GSI conventions |
