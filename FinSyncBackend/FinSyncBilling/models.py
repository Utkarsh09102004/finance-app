from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from FinSyncOrganizations.models import Organization, SubscriptionPlan
import uuid

User = get_user_model()


class Payment(models.Model):
    """Tracks individual payment transactions"""
    PAYMENT_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('REFUNDED', 'Refunded'),
        ('PARTIALLY_REFUNDED', 'Partially Refunded'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('CARD', 'Credit/Debit Card'),
        ('UPI', 'UPI'),
        ('NETBANKING', 'Net Banking'),
        ('WALLET', 'Wallet'),
        ('EMI', 'EMI'),
        ('OTHER', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='payments')
    razorpay_payment_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    razorpay_order_id = models.CharField(max_length=255, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='INR')
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='PENDING')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    failure_reason = models.TextField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['razorpay_payment_id']),
        ]
    
    def __str__(self):
        return f"Payment {self.razorpay_payment_id or self.id} - {self.organization.name}"


class Invoice(models.Model):
    """Tracks invoices generated for subscriptions"""
    INVOICE_STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SENT', 'Sent'),
        ('PAID', 'Paid'),
        ('PARTIALLY_PAID', 'Partially Paid'),
        ('OVERDUE', 'Overdue'),
        ('VOID', 'Void'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='invoices')
    invoice_number = models.CharField(max_length=100, unique=True)
    razorpay_invoice_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    subscription_plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='INR')
    status = models.CharField(max_length=20, choices=INVOICE_STATUS_CHOICES, default='DRAFT')
    billing_period_start = models.DateTimeField()
    billing_period_end = models.DateTimeField()
    due_date = models.DateTimeField()
    paid_at = models.DateTimeField(null=True, blank=True)
    payment = models.OneToOneField(Payment, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoice')
    invoice_url = models.URLField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['invoice_number']),
            models.Index(fields=['due_date']),
        ]
    
    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.organization.name}"
    
    def save(self, *args, **kwargs):
        if not self.invoice_number:
            # Generate invoice number: INV-YYYY-MM-XXXXX
            from datetime import datetime
            year_month = datetime.now().strftime('%Y-%m')
            last_invoice = Invoice.objects.filter(
                invoice_number__startswith=f'INV-{year_month}-'
            ).order_by('-invoice_number').first()
            
            if last_invoice:
                last_number = int(last_invoice.invoice_number.split('-')[-1])
                new_number = last_number + 1
            else:
                new_number = 1
            
            self.invoice_number = f'INV-{year_month}-{new_number:05d}'
        
        super().save(*args, **kwargs)


class SubscriptionHistory(models.Model):
    """Tracks subscription changes and history"""
    ACTION_CHOICES = [
        ('CREATED', 'Created'),
        ('UPGRADED', 'Upgraded'),
        ('DOWNGRADED', 'Downgraded'),
        ('RENEWED', 'Renewed'),
        ('CANCELLED', 'Cancelled'),
        ('EXPIRED', 'Expired'),
        ('REACTIVATED', 'Reactivated'),
        ('PAUSED', 'Paused'),
        ('RESUMED', 'Resumed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='subscription_history')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    from_plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True, related_name='history_from')
    to_plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True, related_name='history_to')
    razorpay_subscription_id = models.CharField(max_length=255, null=True, blank=True)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    reason = models.TextField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'created_at']),
            models.Index(fields=['action']),
        ]
    
    def __str__(self):
        return f"{self.action} - {self.organization.name} - {self.created_at}"


class BillingEvent(models.Model):
    """Audit trail for all billing-related events"""
    EVENT_TYPE_CHOICES = [
        ('PAYMENT_INITIATED', 'Payment Initiated'),
        ('PAYMENT_COMPLETED', 'Payment Completed'),
        ('PAYMENT_FAILED', 'Payment Failed'),
        ('PAYMENT_REFUNDED', 'Payment Refunded'),
        ('SUBSCRIPTION_CREATED', 'Subscription Created'),
        ('SUBSCRIPTION_UPDATED', 'Subscription Updated'),
        ('SUBSCRIPTION_CANCELLED', 'Subscription Cancelled'),
        ('SUBSCRIPTION_EXPIRED', 'Subscription Expired'),
        ('INVOICE_GENERATED', 'Invoice Generated'),
        ('INVOICE_SENT', 'Invoice Sent'),
        ('INVOICE_PAID', 'Invoice Paid'),
        ('WEBHOOK_RECEIVED', 'Webhook Received'),
        ('WEBHOOK_PROCESSED', 'Webhook Processed'),
        ('WEBHOOK_FAILED', 'Webhook Failed'),
        ('TRIAL_STARTED', 'Trial Started'),
        ('TRIAL_ENDING_REMINDER', 'Trial Ending Reminder'),
        ('TRIAL_EXPIRED', 'Trial Expired'),
        ('PAYMENT_METHOD_ADDED', 'Payment Method Added'),
        ('PAYMENT_METHOD_REMOVED', 'Payment Method Removed'),
        ('PAYMENT_RETRY', 'Payment Retry'),
        ('ACCOUNT_SUSPENDED', 'Account Suspended'),
        ('ACCOUNT_REACTIVATED', 'Account Reactivated'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='billing_events')
    event_type = models.CharField(max_length=30, choices=EVENT_TYPE_CHOICES)
    description = models.TextField()
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'event_type', 'created_at']),
            models.Index(fields=['event_type']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.event_type} - {self.organization.name} - {self.created_at}"


class PaymentMethod(models.Model):
    """Stores tokenized payment methods for organizations"""
    METHOD_TYPE_CHOICES = [
        ('CARD', 'Card'),
        ('UPI', 'UPI'),
        ('NETBANKING', 'Net Banking'),
        ('EMANDATE', 'E-Mandate'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='payment_methods')
    razorpay_token_id = models.CharField(max_length=255, unique=True)
    method_type = models.CharField(max_length=20, choices=METHOD_TYPE_CHOICES)
    last_four_digits = models.CharField(max_length=4, null=True, blank=True)  # For cards
    card_network = models.CharField(max_length=50, null=True, blank=True)  # Visa, Mastercard, etc.
    bank_name = models.CharField(max_length=100, null=True, blank=True)  # For netbanking
    upi_id = models.CharField(max_length=100, null=True, blank=True)  # For UPI
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)  # For cards
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_default', '-created_at']
        indexes = [
            models.Index(fields=['organization', 'is_active']),
        ]
    
    def __str__(self):
        if self.method_type == 'CARD':
            return f"Card ending in {self.last_four_digits} - {self.organization.name}"
        return f"{self.method_type} - {self.organization.name}"
    
    def save(self, *args, **kwargs):
        # Ensure only one default payment method per organization
        if self.is_default:
            PaymentMethod.objects.filter(
                organization=self.organization,
                is_default=True
            ).exclude(id=self.id).update(is_default=False)
        super().save(*args, **kwargs)


class PaymentRetryLog(models.Model):
    """Tracks payment retry attempts for failed payments"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='retry_logs')
    attempt_number = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=Payment.PAYMENT_STATUS_CHOICES)
    failure_reason = models.TextField(null=True, blank=True)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['payment', 'attempt_number']
        unique_together = [['payment', 'attempt_number']]
    
    def __str__(self):
        return f"Retry #{self.attempt_number} for Payment {self.payment.id}"