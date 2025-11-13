# FinSync Backend - Comprehensive Documentation

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Authentication System (FinSyncAuth)](#authentication-system-finsyncauth)
4. [Organization Management (FinSyncOrganizations)](#organization-management-finsyncorganizations)
5. [Integration System (FinSyncIntegrations)](#integration-system-finsyncintegrations)
6. [Billing System (FinSyncBilling)](#billing-system-finsyncbilling)
7. [Core Settings and Configuration](#core-settings-and-configuration)
8. [API Endpoints Reference](#api-endpoints-reference)
9. [Business Logic Summary](#business-logic-summary)
10. [Security Considerations](#security-considerations)
11. [Development Guidelines](#development-guidelines)

---

## Overview

FinSync Backend is a Django-based multi-tenant SaaS application designed for financial data synchronization and management. The system provides:

- **Multi-tenant Architecture**: Every user belongs to exactly one organization
- **JWT Authentication**: Stateless authentication with token refresh
- **External Integrations**: OAuth-based connections to accounting software (Zoho Books, QuickBooks)
- **Subscription Management**: Trial periods, paid plans, and Razorpay payment integration
- **Comprehensive Audit Trails**: Detailed logging of all critical operations

### Technology Stack
- **Framework**: Django 5.0.1
- **API**: Django REST Framework 3.14.0
- **Authentication**: djangorestframework-simplejwt 5.3.1, dj-rest-auth 5.0.2
- **Social Auth**: django-allauth 0.61.1
- **Payment Gateway**: Razorpay (razorpay 1.4.1)
- **Database**: SQLite (dev) / PostgreSQL (production)

---

## Architecture

### Directory Structure
```
FinSyncBackend/
├── FinSyncBackend/          # Main Django project configuration
├── FinSyncAuth/             # Authentication & user management
├── FinSyncOrganizations/    # Organization & subscription management
├── FinSyncIntegrations/     # External service integrations
│   └── providers/           # Provider-specific implementations
│       └── zohobooks/       # Zoho Books integration
└── FinSyncBilling/          # Billing & payment processing
    └── management/commands/ # Cron jobs for billing
```

### Key Design Principles
1. **Mandatory Organization Membership**: Every user must belong to an organization
2. **Email-based Authentication**: No username field; email is the primary identifier
3. **Provider Pattern**: Extensible integration system for external services
4. **Audit Everything**: Comprehensive logging for compliance and debugging
5. **Trial-first Approach**: New organizations start with a 14-day trial

---

## Authentication System (FinSyncAuth)

### User Model Structure

#### CustomUser Model
The system uses a custom user model extending Django's AbstractUser:

```python
class CustomUser(AbstractUser):
    email = models.EmailField(unique=True, db_index=True)
    organization = models.ForeignKey(Organization, on_delete=CASCADE)
    username = None  # Removed in favor of email
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
```

**Key Features:**
- Email as primary identifier (username field removed)
- Mandatory organization association
- Custom user manager for organization-aware user creation
- Helper method `get_domain()` extracts domain from email

### Authentication Flow

#### Registration Process
1. **Three Paths to Registration:**
   - **With Invite Code**: Join existing organization
   - **With Organization Name**: Create new organization as owner
   - **Default**: Create personal workspace ("{email}'s Workspace")

2. **Validation Steps:**
   - Email uniqueness check
   - Password confirmation
   - Invite code validation (if provided):
     - Check code exists and is active
     - Verify not expired
     - Confirm email match (if invite is email-specific)
     - Ensure organization has capacity

3. **Organization Assignment:**
   ```python
   # With invite code
   user.organization = invite.organization
   invite.mark_used(user)
   
   # With organization name
   organization = Organization.objects.create(
       name=org_name,
       created_by=user,
       owner=user
   )
   user.organization = organization
   
   # Default personal workspace
   organization = Organization.objects.create(
       name=f"{user.email}'s Workspace",
       created_by=user,
       owner=user
   )
   ```

4. **Email Verification**: Mandatory by default (`ACCOUNT_EMAIL_VERIFICATION = 'mandatory'`)

#### JWT Token Management
```python
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'AUTH_HEADER_TYPES': ('Bearer',),
}
```

**Token Endpoints:**
- Login: Returns both access and refresh tokens
- Refresh: `POST /api/auth/token/refresh/`
- Verify: `POST /api/auth/token/verify/`

### Social Authentication
- **Provider**: Google OAuth2
- **Configuration**: PKCE enabled for security
- **Behavior**: Always creates individual workspace (no domain-based joining)

### API Endpoints
- `POST /api/auth/registration/` - User registration
- `POST /api/auth/login/` - User login (returns JWT tokens)
- `POST /api/auth/logout/` - User logout
- `GET /api/auth/user/` - Current user details
- `PUT/PATCH /api/auth/user/` - Update user details
- `POST /api/auth/password/reset/` - Request password reset
- `POST /api/auth/password/change/` - Change password
- `GET /api/auth/users/` - List users in organization

---

## Organization Management (FinSyncOrganizations)

### Models

#### Organization Model
Central entity representing customer workspaces:

```python
class Organization(models.Model):
    name = models.CharField(max_length=255)
    domain = models.CharField(max_length=255, unique=True, null=True)
    created_by = models.ForeignKey(User, related_name='created_organizations')
    owner = models.ForeignKey(User, related_name='owned_organizations')
    
    # Subscription fields
    subscription_plan = models.ForeignKey(SubscriptionPlan, on_delete=PROTECT)
    subscription_status = models.CharField(choices=SUBSCRIPTION_STATUS_CHOICES)
    trial_ends_at = models.DateTimeField(null=True)
    
    # Razorpay integration
    razorpay_customer_id = models.CharField(max_length=255, null=True)
    razorpay_subscription_id = models.CharField(max_length=255, null=True)
    
    # Billing information
    billing_email = models.EmailField(null=True)
    billing_name = models.CharField(max_length=255, null=True)
    billing_phone = models.CharField(max_length=20, null=True)
```

**Key Methods:**
- `can_add_user()`: Checks against plan limits
- `can_add_integration()`: Checks against plan limits
- `get_active_user_count()`: Current active users
- `get_active_integration_count()`: Current active integrations

#### SubscriptionPlan Model
Defines available plans and their limits:

```python
class SubscriptionPlan(models.Model):
    name = models.CharField(primary_key=True, choices=PLAN_CHOICES)
    display_name = models.CharField(max_length=100)
    max_users = models.PositiveIntegerField(default=1)
    max_integrations = models.PositiveIntegerField(default=1)
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2)
    is_trial = models.BooleanField(default=False)
    trial_duration_days = models.PositiveIntegerField(null=True)
```

**Available Plans:**
- **Trial**: 14 days, 1 user, 1 integration (Free)
- **Individual**: ₹299/month, 1 user, 3 integrations
- **Team**: ₹999/month, 10 users, 5 integrations

#### OrganizationInvite Model
Manages invitations to join organizations:

```python
class OrganizationInvite(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    organization = models.ForeignKey(Organization)
    code = models.CharField(unique=True, default=default_invite_code)
    email = models.EmailField(null=True)  # Optional email restriction
    created_by = models.ForeignKey(User)
    expires_at = models.DateTimeField(default=default_invite_expiry)
    is_active = models.BooleanField(default=True)
```

**Invite Code Format**: `ORG-XXXXXXXX` (8 random characters)
**Default Expiry**: 7 days

### Organization Management Features

#### Invite System
1. **Creating Invites:**
   - Organization members can create invites
   - Optional email restriction for specific users
   - 7-day expiry by default
   - Unique code generation

2. **Accepting Invites:**
   - Validates code existence and active status
   - Checks expiry date
   - Verifies email match (if restricted)
   - Ensures organization capacity
   - Moves user to new organization
   - Creates audit log entry

3. **Invite Validation:**
   ```python
   # Check if invite is valid
   if not invite.is_active:
       raise ValidationError("Invite is no longer active")
   
   if invite.expires_at < timezone.now():
       raise ValidationError("Invite has expired")
   
   if invite.email and invite.email != user.email:
       raise PermissionDenied("Invite is for different email")
   
   if not organization.can_add_user():
       raise ValidationError("Organization at capacity")
   ```

#### Member Management
1. **Leave Organization:**
   - Creates new personal workspace
   - Transfers user to new organization
   - Logs membership change

2. **Remove Member (Owner only):**
   - Creates personal workspace for removed user
   - Transfers user to new organization
   - Logs removal with actor

3. **Change Owner:**
   - Only current owner can transfer ownership
   - New owner must be organization member
   - Logs ownership change

### Permissions
- `IsOrganizationMember`: Validates user belongs to organization
- `IsOrganizationOwner`: Validates user is organization owner

### API Endpoints
- `POST /api/organizations/create/` - Create new organization
- `GET /api/organizations/my-organization/` - Current user's organization
- `GET /api/organizations/{id}/invites/` - List organization invites
- `POST /api/organizations/{id}/invites/` - Create new invite
- `POST /api/organizations/invites/accept/` - Accept invite
- `POST /api/organizations/leave/` - Leave current organization
- `POST /api/organizations/{id}/change-owner/` - Transfer ownership
- `POST /api/organizations/{id}/members/{user_id}/remove/` - Remove member

---

## Integration System (FinSyncIntegrations)

### Architecture
The integration system uses a provider pattern for extensibility:

```
FinSyncIntegrations/
├── models.py           # Core integration models
├── common_views.py     # Generic integration views
├── middleware.py       # OAuth session handling
└── providers/
    └── zohobooks/
        ├── views.py    # Zoho-specific views
        └── utils.py    # Zoho helper functions
```

### Models

#### Integration Model
Represents connections to external services:

```python
class Integration(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    organization = models.ForeignKey(Organization)
    provider = models.CharField(choices=PROVIDER_CHOICES)
    external_id = models.CharField(max_length=255, null=True)
    name = models.CharField(max_length=255)
    connection_status = models.CharField(choices=STATUS_CHOICES)
    
    # Token storage (TODO: Implement encryption)
    access_token_encrypted = models.TextField(null=True)
    refresh_token_encrypted = models.TextField(null=True)
    token_expiry = models.DateTimeField(null=True)
    
    # Metadata
    added_by_user = models.ForeignKey(User)
    last_successful_sync = models.DateTimeField(null=True)
    last_sync_error = models.TextField(null=True)
```

**Connection Status Values:**
- `CONNECTED`: Fully operational
- `DISCONNECTED`: Manually disconnected
- `NEEDS_REAUTH`: Token expired/revoked
- `ERROR`: Connection failure
- `PENDING_EXTERNAL_ID`: Awaiting organization selection

#### OAuthState Model
CSRF protection for OAuth flows:

```python
class OAuthState(models.Model):
    state = models.CharField(unique=True)
    user = models.ForeignKey(User)
    organization = models.ForeignKey(Organization)
    provider = models.CharField(max_length=50)
    additional_data = models.JSONField(null=True)
    expires_at = models.DateTimeField()
```

**Features:**
- 10-minute expiry
- One-time use (deleted after validation)
- Stores provider-specific data

### OAuth Flow Implementation

#### 1. Initiation
```python
# ZohoBooksInitiateView
def get(self, request):
    # Create state for CSRF protection
    state_value = get_random_string(32)
    OAuthState.objects.create(
        state=state_value,
        user=request.user,
        organization=request.user.organization,
        provider='zohobooks',
        expires_at=timezone.now() + timedelta(minutes=10)
    )
    
    # Build authorization URL
    auth_url = f"{ZOHO_AUTHORIZATION_URL}?{params}"
    return Response({"authorization_url": auth_url, "state": state_value})
```

#### 2. Callback Processing
```python
# ZohoBooksCallbackView
def get(self, request):
    # Validate state
    state = request.GET.get('state')
    oauth_state = OAuthState.objects.get(state=state)
    
    # Exchange code for tokens
    token_response = requests.post(ZOHO_TOKEN_URL, data={
        'code': request.GET.get('code'),
        'client_id': ZOHO_CLIENT_ID,
        'client_secret': ZOHO_CLIENT_SECRET,
        'redirect_uri': ZOHO_REDIRECT_URI,
        'grant_type': 'authorization_code'
    })
    
    # Create integration with PENDING_EXTERNAL_ID status
    integration = Integration.objects.create(
        organization=oauth_state.organization,
        provider='zohobooks',
        connection_status='PENDING_EXTERNAL_ID',
        access_token_encrypted=tokens['access_token'],
        refresh_token_encrypted=tokens['refresh_token'],
        token_expiry=expiry_time
    )
```

#### 3. External Organization Selection
```python
# Fetch available organizations
def fetch_external_organizations(integration):
    token = get_valid_access_token(integration)
    response = requests.get(
        f"{ZOHO_API_BASE_URL}/organizations",
        headers={"Authorization": f"Zoho-oauthtoken {token}"}
    )
    return response.json()['organizations']

# Set selected organization
def set_external_organization(integration, external_id):
    integration.external_id = external_id
    integration.connection_status = 'CONNECTED'
    integration.save()
```

### Token Management

#### Automatic Token Refresh
```python
def get_valid_access_token(integration):
    # Check if token is expired (with 5-minute buffer)
    if integration.token_expiry <= timezone.now() + timedelta(minutes=5):
        return refresh_zoho_token(integration)
    return integration.access_token_encrypted

def refresh_zoho_token(integration):
    response = requests.post(ZOHO_TOKEN_URL, data={
        'refresh_token': integration.refresh_token_encrypted,
        'client_id': ZOHO_CLIENT_ID,
        'client_secret': ZOHO_CLIENT_SECRET,
        'grant_type': 'refresh_token'
    })
    
    if response.status_code == 200:
        # Update tokens
        integration.access_token_encrypted = new_token
        integration.token_expiry = new_expiry
        integration.save()
    else:
        # Handle refresh failure
        integration.connection_status = 'NEEDS_REAUTH'
        integration.save()
```

### Security Considerations
- **Token Storage**: Currently unencrypted (marked as TODO)
- **State Validation**: One-time use with expiry
- **Organization Access**: Enforced at view level
- **Session Middleware**: Handles OAuth redirects

### API Endpoints
- `GET /api/integrations/` - List all integrations
- `GET /api/integrations/{id}/` - Get integration details
- `DELETE /api/integrations/{id}/` - Remove integration
- `GET /api/integrations/zohobooks/initiate/` - Start OAuth flow
- `GET /api/integrations/zohobooks/callback/` - OAuth callback
- `GET /api/integrations/zohobooks/{id}/fetch-external-organizations/` - Get Zoho orgs
- `POST /api/integrations/zohobooks/{id}/set-external-organization/` - Set Zoho org

---

## Billing System (FinSyncBilling)

### Overview
Comprehensive billing system integrated with Razorpay for:
- Subscription lifecycle management
- Payment processing
- Invoice generation
- Webhook handling
- Payment retry mechanism

### Models

#### Payment Model
Tracks all payment transactions:

```python
class Payment(models.Model):
    organization = models.ForeignKey(Organization)
    razorpay_payment_id = models.CharField(unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(default='INR')
    status = models.CharField(choices=PAYMENT_STATUS_CHOICES)
    payment_method = models.CharField(choices=PAYMENT_METHOD_CHOICES)
    failure_reason = models.TextField(null=True)
    paid_at = models.DateTimeField(null=True)
```

**Status Values:**
- PENDING, PROCESSING, COMPLETED, FAILED, REFUNDED, PARTIALLY_REFUNDED

#### Invoice Model
Auto-generated invoices with sequential numbering:

```python
class Invoice(models.Model):
    organization = models.ForeignKey(Organization)
    invoice_number = models.CharField(unique=True)  # Format: INV-YYYY-MM-XXXXX
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(choices=INVOICE_STATUS_CHOICES)
    billing_period_start = models.DateField()
    billing_period_end = models.DateField()
    due_date = models.DateField()
    payment = models.OneToOneField(Payment, null=True)
```

**Auto-numbering Example**: INV-2025-06-00001

#### BillingEvent Model
Comprehensive audit trail:

```python
class BillingEvent(models.Model):
    event_type = models.CharField(choices=EVENT_TYPE_CHOICES)
    organization = models.ForeignKey(Organization, null=True)
    user = models.ForeignKey(User, null=True)
    description = models.TextField()
    metadata = models.JSONField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

**Event Types:**
- Payment events: INITIATED, COMPLETED, FAILED
- Subscription events: CREATED, UPDATED, CANCELLED
- Invoice events: GENERATED, SENT, PAID
- Webhook events: RECEIVED, PROCESSED, FAILED

### Razorpay Integration

#### RazorpayService Class
Centralized payment gateway operations:

```python
class RazorpayService:
    def create_customer(self, organization):
        """Creates Razorpay customer profile"""
        
    def create_subscription(self, organization, plan):
        """Initiates new subscription"""
        
    def update_subscription(self, organization, new_plan):
        """Handles plan changes"""
        
    def cancel_subscription(self, organization):
        """Processes cancellation"""
        
    def create_payment_link(self, organization, amount):
        """Generates checkout links"""
        
    def retry_payment(self, organization):
        """Handles failed payment retries"""
```

#### Mock Mode
When `ENABLE_PAYMENTS=False`, returns mock responses for development.

### Webhook Processing

#### Security
- Signature verification using `X-Razorpay-Signature`
- All webhooks logged to BillingEvent table

#### Handled Events
1. **Subscription Webhooks:**
   - `subscription.activated`: New subscription active
   - `subscription.charged`: Successful renewal
   - `subscription.updated`: Plan changes
   - `subscription.cancelled`: Cancellation processed
   - `subscription.halted`: Payment failures

2. **Payment Webhooks:**
   - `payment.captured`: Payment successful
   - `payment.failed`: Payment failure
     ```python
     # On first failure
     organization.payment_failed_count += 1
     organization.grace_period_ends_at = now + timedelta(days=7)
     organization.subscription_status = 'PAST_DUE'
     ```

### Subscription Lifecycle

#### Trial Period
1. **Creation**: 14-day trial on organization creation
2. **Monitoring**: Daily cron job checks:
   - 3-day reminder
   - 1-day reminder
   - Expiry handling
3. **Conversion**: Must select paid plan before expiry

#### Grace Period
- **Trigger**: First payment failure
- **Duration**: 7 days
- **Service**: Continues with PAST_DUE status
- **Expiry**: Account suspended

### Payment Retry Mechanism
```python
# Configuration
PAYMENT_RETRY_ATTEMPTS = 3
PAYMENT_RETRY_INTERVAL_HOURS = 24

# Retry logic
if payment.status == 'FAILED' and retry_count < max_attempts:
    schedule_retry(payment, retry_count + 1)
```

### Management Commands

#### check_subscriptions
Daily maintenance tasks:
```bash
python manage.py check_subscriptions [--dry-run]
```
- Processes expired trials
- Sends reminders
- Handles payment retries
- Manages grace periods

#### setup_subscription_plans
Initialize subscription plans:
```bash
python manage.py setup_subscription_plans
```

### API Endpoints
- `GET /api/billing/pricing/` - Available plans
- `GET /api/billing/overview/` - Billing dashboard
- `POST /api/billing/checkout/` - Create checkout
- `POST /api/billing/subscription/change/` - Change plan
- `POST /api/billing/subscription/cancel/` - Cancel subscription
- `GET /api/billing/invoices/` - List invoices
- `GET /api/billing/invoices/{id}/download/` - Download invoice
- `POST /api/billing/webhooks/razorpay/` - Webhook handler

---

## Core Settings and Configuration

### Environment Variables
The application uses environment variables for configuration:

```bash
# Django Settings
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (Production)
DB_ENGINE=django.db.backends.postgresql
DB_NAME=finsync_db
DB_USER=finsync_user
DB_PASSWORD=secure_password
DB_HOST=localhost
DB_PORT=5432

# JWT Configuration
JWT_ACCESS_TOKEN_LIFETIME_MINUTES=60
JWT_REFRESH_TOKEN_LIFETIME_DAYS=7
JWT_ROTATE_REFRESH_TOKENS=True

# CORS Settings
CORS_ALLOW_ALL_ORIGINS=True
CORS_ALLOW_CREDENTIALS=True

# Organization Settings
ADMIN_ORG_NAME=SuperAdmin Organization
DEFAULT_TRIAL_DURATION_DAYS=14
DEFAULT_INVITE_EXPIRY_DAYS=7

# Zoho Integration
ZOHO_CLIENT_ID=your-zoho-client-id
ZOHO_CLIENT_SECRET=your-zoho-client-secret
ZOHO_REDIRECT_URI=http://localhost:8000/api/integrations/zohobooks/callback/
ZOHO_AUTHORIZATION_URL=https://accounts.zoho.com/oauth/v2/auth
ZOHO_TOKEN_URL=https://accounts.zoho.com/oauth/v2/token
ZOHO_SCOPES=ZohoBooks.fullaccess.all
ZOHO_API_BASE_URL=https://books.zoho.com/api/v3

# Razorpay Configuration
RAZORPAY_KEY_ID=your-razorpay-key
RAZORPAY_KEY_SECRET=your-razorpay-secret
RAZORPAY_WEBHOOK_SECRET=your-webhook-secret
RAZORPAY_TEST_MODE=True
ENABLE_PAYMENTS=False

# Payment Settings
PAYMENT_RETRY_ATTEMPTS=3
PAYMENT_RETRY_INTERVAL_HOURS=24
PAYMENT_GRACE_PERIOD_DAYS=7

# Frontend URLs
FRONTEND_BASE_URL=http://localhost:3000
FRONTEND_INTEGRATION_SUCCESS_URL=http://localhost:3000/integrations
FRONTEND_INTEGRATION_FAILURE_URL=http://localhost:3000/integrations/error
FRONTEND_INTEGRATION_PENDING_CONFIG_URL=http://localhost:3000/integrations/configure
FRONTEND_PAYMENT_SUCCESS_URL=http://localhost:3000/billing/success
FRONTEND_PAYMENT_FAILURE_URL=http://localhost:3000/billing/failure
```

### Django Settings Structure

#### Application Organization
```python
SYSTEM_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites'
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework.authtoken',
    'dj_rest_auth',
    'dj_rest_auth.registration',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
]

USER_DEFINED_APPS = [
    'FinSyncAuth',
    'FinSyncOrganizations',
    'FinSyncIntegrations',
    'FinSyncBilling'
]

INSTALLED_APPS = USER_DEFINED_APPS + SYSTEM_APPS + THIRD_PARTY_APPS
```

#### Middleware Configuration
```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'FinSyncIntegrations.middleware.OAuthSessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]
```

#### Authentication Configuration
```python
# Custom User Model
AUTH_USER_MODEL = 'FinSyncAuth.CustomUser'

# Django-allauth Settings
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_ADAPTER = 'FinSyncAuth.adapter.CustomAccountAdapter'

# Social Account Adapter
SOCIALACCOUNT_ADAPTER = 'FinSyncAuth.adapter.CustomSocialAccountAdapter'
```

### Subscription Pricing Configuration
```python
SUBSCRIPTION_PRICING = {
    'individual': {
        'monthly': Decimal('299.00'),
        'max_users': 1,
        'max_integrations': 3
    },
    'team': {
        'monthly': Decimal('999.00'),
        'max_users': 10,
        'max_integrations': 5
    }
}
```

---

## API Endpoints Reference

### Authentication Endpoints
Base URL: `/api/auth/`

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/registration/` | Register new user | No |
| POST | `/login/` | Login (returns JWT) | No |
| POST | `/logout/` | Logout | Yes |
| GET | `/user/` | Get current user | Yes |
| PUT/PATCH | `/user/` | Update user | Yes |
| POST | `/password/reset/` | Request password reset | No |
| POST | `/password/reset/confirm/` | Confirm password reset | No |
| POST | `/password/change/` | Change password | Yes |
| POST | `/token/refresh/` | Refresh JWT token | No |
| POST | `/token/verify/` | Verify JWT token | No |
| GET | `/users/` | List organization users | Yes |
| GET | `/registration/account-confirm-email/<key>/` | Confirm email | No |

### Organization Endpoints
Base URL: `/api/organizations/`

| Method | Endpoint | Description | Auth Required | Permission |
|--------|----------|-------------|---------------|------------|
| POST | `/create/` | Create organization | Yes | Authenticated |
| GET | `/my-organization/` | Get user's organization | Yes | Authenticated |
| GET | `/{id}/invites/` | List invites | Yes | Organization Member |
| POST | `/{id}/invites/` | Create invite | Yes | Organization Member |
| POST | `/invites/accept/` | Accept invite | Yes | Authenticated |
| POST | `/leave/` | Leave organization | Yes | Authenticated |
| POST | `/{id}/change-owner/` | Transfer ownership | Yes | Organization Owner |
| POST | `/{id}/members/{user_id}/remove/` | Remove member | Yes | Organization Owner |

### Integration Endpoints
Base URL: `/api/integrations/`

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/` | List integrations | Yes |
| GET | `/{id}/` | Get integration | Yes |
| PUT/PATCH | `/{id}/` | Update integration | Yes |
| DELETE | `/{id}/` | Delete integration | Yes |

#### Zoho Books Endpoints
| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/zohobooks/initiate/` | Start OAuth flow | Yes |
| GET | `/zohobooks/callback/` | OAuth callback | No |
| GET | `/zohobooks/{id}/fetch-external-organizations/` | Get Zoho organizations | Yes |
| POST | `/zohobooks/{id}/set-external-organization/` | Set Zoho organization | Yes |

### Billing Endpoints
Base URL: `/api/billing/`

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/pricing/` | Get available plans | No |
| GET | `/overview/` | Billing overview | Yes |
| POST | `/checkout/` | Create checkout session | Yes |
| POST | `/subscription/change/` | Change subscription | Yes |
| POST | `/subscription/cancel/` | Cancel subscription | Yes |
| GET | `/payment-methods/` | List payment methods | Yes |
| POST | `/payment-methods/add/` | Add payment method | Yes |
| DELETE | `/payment-methods/{id}/remove/` | Remove payment method | Yes |
| GET | `/invoices/` | List invoices | Yes |
| GET | `/invoices/{id}/download/` | Download invoice | Yes |
| POST | `/billing-info/update/` | Update billing info | Yes |
| POST | `/webhooks/razorpay/` | Razorpay webhook | No |

---

## Business Logic Summary

### User Onboarding Flow
1. **Registration Options:**
   - Join via invite code → Existing organization member
   - Create with organization name → New organization owner
   - Default registration → Personal workspace owner

2. **Trial Assignment:**
   - All new organizations get 14-day trial
   - 1 user, 1 integration limits
   - Automatic reminders at 3 days and 1 day

3. **Email Verification:**
   - Mandatory before accessing system
   - Confirmation link sent automatically
   - Redirects to frontend after confirmation

### Organization Lifecycle
1. **Creation:**
   - Owner assigned
   - Trial plan applied
   - Domain extracted (if not free email)

2. **Growth:**
   - Invite members (respects plan limits)
   - Add integrations (respects plan limits)
   - Upgrade subscription as needed

3. **Management:**
   - Owner can transfer ownership
   - Owner can remove members
   - Members can leave (get personal workspace)

### Integration Lifecycle
1. **Connection:**
   - OAuth flow initiated
   - Tokens stored (pending encryption)
   - External organization selected

2. **Usage:**
   - Automatic token refresh
   - Error handling with status updates
   - Sync tracking

3. **Disconnection:**
   - Manual disconnect available
   - Automatic on token failure
   - Cleanup of stored tokens

### Billing Lifecycle
1. **Trial Period:**
   - 14 days free
   - Full feature access
   - Reminders before expiry

2. **Paid Subscription:**
   - Monthly billing cycle
   - Automatic renewals
   - Invoice generation

3. **Payment Failure:**
   - 7-day grace period
   - Retry attempts (3x)
   - Service suspension after grace

### Capacity Management
Organizations have limits based on their subscription:

```python
# Check before adding user
if not organization.can_add_user():
    raise ValidationError("User limit reached")

# Check before adding integration
if not organization.can_add_integration():
    raise ValidationError("Integration limit reached")
```

### Audit Trail
All critical operations are logged:
- User registration and login
- Organization membership changes
- Integration connections
- Payment transactions
- Subscription changes

---

## Security Considerations

### Authentication Security
1. **JWT Tokens:**
   - Access token: 60-minute expiry
   - Refresh token: 7-day expiry
   - Token rotation on refresh
   - Blacklist support available

2. **Password Security:**
   - Email verification required
   - Password reset via email
   - Django's password validators available

### Data Protection
1. **Current Issues:**
   - **Token Storage**: Integration tokens stored unencrypted (TODO)
   - Recommendation: Implement django-encrypted-fields

2. **Access Control:**
   - Organization-based isolation
   - Owner-only administrative actions
   - Member permissions for standard operations

### API Security
1. **CORS Configuration:**
   - Credentials allowed
   - Origin validation in production

2. **CSRF Protection:**
   - Enabled except for webhooks
   - JWT removes need for CSRF in API

3. **Webhook Security:**
   - Signature verification
   - IP whitelisting recommended

### Best Practices
1. **Environment Variables:**
   - Never commit secrets
   - Use strong, unique values
   - Rotate regularly

2. **Database Security:**
   - Use PostgreSQL in production
   - Enable SSL connections
   - Regular backups

3. **Monitoring:**
   - Log all authentication attempts
   - Track failed payments
   - Monitor integration errors

---

## Development Guidelines

### Code Organization
1. **App Structure:**
   - Models: Data definitions
   - Views: Business logic
   - Serializers: Data validation
   - URLs: Endpoint routing
   - Utils: Helper functions

2. **Naming Conventions:**
   - Models: Singular (Organization, not Organizations)
   - Views: Descriptive actions (OrganizationCreateAPIView)
   - URLs: RESTful patterns (/organizations/{id}/invites/)

### Testing Approach
1. **Unit Tests:**
   - Model methods
   - Serializer validation
   - Utility functions

2. **Integration Tests:**
   - API endpoints
   - OAuth flows
   - Webhook processing

3. **End-to-End Tests:**
   - User registration flow
   - Organization management
   - Payment processing

### Error Handling
1. **Consistent Responses:**
   ```python
   {
       "detail": "Error message",
       "code": "ERROR_CODE",
       "field_errors": {
           "field_name": ["Error message"]
       }
   }
   ```

2. **Logging:**
   - Use appropriate log levels
   - Include context (user, organization)
   - Avoid logging sensitive data

### Database Migrations
1. **Best Practices:**
   - Review auto-generated migrations
   - Test rollback scenarios
   - Document breaking changes

2. **Data Migrations:**
   - Use RunPython for complex changes
   - Provide reverse operations
   - Test with production-like data

### API Versioning
Consider implementing versioning strategy:
- URL versioning: `/api/v1/`
- Header versioning: `Accept: application/vnd.finsync.v1+json`
- Query parameter: `?version=1`

### Performance Optimization
1. **Database Queries:**
   - Use select_related() for ForeignKeys
   - Use prefetch_related() for reverse relations
   - Add database indexes for frequent queries

2. **Caching:**
   - Cache subscription plan lookups
   - Cache organization member counts
   - Use Redis for production

3. **Background Tasks:**
   - Email sending
   - Webhook processing
   - Report generation

### Deployment Checklist
1. **Environment:**
   - Set DEBUG=False
   - Configure allowed hosts
   - Set strong SECRET_KEY

2. **Database:**
   - Use PostgreSQL
   - Enable connection pooling
   - Configure backups

3. **Security:**
   - Enable HTTPS
   - Configure security headers
   - Set up monitoring

4. **Performance:**
   - Configure caching
   - Set up CDN for static files
   - Enable compression

---

## Conclusion

FinSync Backend provides a robust foundation for a multi-tenant SaaS application with:
- Comprehensive authentication and authorization
- Flexible organization management
- Extensible integration framework
- Complete billing and subscription system
- Detailed audit trails

The architecture supports growth through:
- Clear separation of concerns
- Extensive use of Django best practices
- Preparation for horizontal scaling
- Security-first design approach

Key areas for improvement:
1. Implement token encryption for integrations
2. Add comprehensive test coverage
3. Set up monitoring and alerting
4. Implement rate limiting
5. Add API documentation (OpenAPI/Swagger)

This documentation serves as a complete guide for understanding, maintaining, and extending the FinSync Backend system.