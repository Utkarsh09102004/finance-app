from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from FinSyncBilling.models import (
    Payment, Invoice, SubscriptionHistory, BillingEvent, PaymentMethod, PaymentRetryLog
)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['id', 'organization_link', 'amount_display', 'status_badge', 'payment_method', 'created_at']
    list_filter = ['status', 'payment_method', 'currency', 'created_at']
    search_fields = ['organization__name', 'razorpay_payment_id', 'razorpay_order_id']
    readonly_fields = ['id', 'created_at', 'updated_at', 'paid_at', 'metadata']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    def organization_link(self, obj):
        url = reverse('admin:FinSyncOrganizations_organization_change', args=[obj.organization.id])
        return format_html('<a href="{}">{}</a>', url, obj.organization.name)
    organization_link.short_description = 'Organization'
    
    def amount_display(self, obj):
        return f"{obj.amount} {obj.currency}"
    amount_display.short_description = 'Amount'
    
    def status_badge(self, obj):
        colors = {
            'PENDING': '#FFA500',
            'PROCESSING': '#1E90FF',
            'COMPLETED': '#32CD32',
            'FAILED': '#DC143C',
            'REFUNDED': '#9370DB',
        }
        color = colors.get(obj.status, '#808080')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.status
        )
    status_badge.short_description = 'Status'


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'organization_link', 'total_amount_display', 'status_badge', 'due_date', 'created_at']
    list_filter = ['status', 'currency', 'created_at', 'due_date']
    search_fields = ['organization__name', 'invoice_number', 'razorpay_invoice_id']
    readonly_fields = ['id', 'invoice_number', 'created_at', 'updated_at', 'metadata']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    def organization_link(self, obj):
        url = reverse('admin:FinSyncOrganizations_organization_change', args=[obj.organization.id])
        return format_html('<a href="{}">{}</a>', url, obj.organization.name)
    organization_link.short_description = 'Organization'
    
    def total_amount_display(self, obj):
        return f"{obj.total_amount} {obj.currency}"
    total_amount_display.short_description = 'Total Amount'
    
    def status_badge(self, obj):
        colors = {
            'DRAFT': '#808080',
            'SENT': '#1E90FF',
            'PAID': '#32CD32',
            'PARTIALLY_PAID': '#FFA500',
            'OVERDUE': '#DC143C',
            'VOID': '#696969',
        }
        color = colors.get(obj.status, '#808080')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.status
        )
    status_badge.short_description = 'Status'


@admin.register(SubscriptionHistory)
class SubscriptionHistoryAdmin(admin.ModelAdmin):
    list_display = ['organization_link', 'action_badge', 'plan_change', 'performed_by', 'created_at']
    list_filter = ['action', 'created_at']
    search_fields = ['organization__name', 'performed_by__email', 'reason']
    readonly_fields = ['id', 'created_at', 'metadata']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    def organization_link(self, obj):
        url = reverse('admin:FinSyncOrganizations_organization_change', args=[obj.organization.id])
        return format_html('<a href="{}">{}</a>', url, obj.organization.name)
    organization_link.short_description = 'Organization'
    
    def action_badge(self, obj):
        colors = {
            'CREATED': '#32CD32',
            'UPGRADED': '#1E90FF',
            'DOWNGRADED': '#FFA500',
            'RENEWED': '#32CD32',
            'CANCELLED': '#DC143C',
            'EXPIRED': '#696969',
            'REACTIVATED': '#32CD32',
            'PAUSED': '#FFA500',
            'RESUMED': '#1E90FF',
        }
        color = colors.get(obj.action, '#808080')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_action_display()
        )
    action_badge.short_description = 'Action'
    
    def plan_change(self, obj):
        if obj.from_plan and obj.to_plan:
            return f"{obj.from_plan.display_name} → {obj.to_plan.display_name}"
        elif obj.to_plan:
            return f"→ {obj.to_plan.display_name}"
        elif obj.from_plan:
            return f"{obj.from_plan.display_name} →"
        return "-"
    plan_change.short_description = 'Plan Change'


@admin.register(BillingEvent)
class BillingEventAdmin(admin.ModelAdmin):
    list_display = ['event_type_badge', 'organization_link', 'description', 'user', 'created_at']
    list_filter = ['event_type', 'created_at']
    search_fields = ['organization__name', 'description', 'user__email']
    readonly_fields = ['id', 'created_at', 'metadata', 'ip_address', 'user_agent']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    def organization_link(self, obj):
        if obj.organization:
            url = reverse('admin:FinSyncOrganizations_organization_change', args=[obj.organization.id])
            return format_html('<a href="{}">{}</a>', url, obj.organization.name)
        return "-"
    organization_link.short_description = 'Organization'
    
    def event_type_badge(self, obj):
        # Group events by category for coloring
        payment_events = ['PAYMENT_INITIATED', 'PAYMENT_COMPLETED', 'PAYMENT_FAILED', 'PAYMENT_REFUNDED', 'PAYMENT_RETRY']
        subscription_events = ['SUBSCRIPTION_CREATED', 'SUBSCRIPTION_UPDATED', 'SUBSCRIPTION_CANCELLED', 'SUBSCRIPTION_EXPIRED']
        invoice_events = ['INVOICE_GENERATED', 'INVOICE_SENT', 'INVOICE_PAID']
        webhook_events = ['WEBHOOK_RECEIVED', 'WEBHOOK_PROCESSED', 'WEBHOOK_FAILED']
        trial_events = ['TRIAL_STARTED', 'TRIAL_ENDING_REMINDER', 'TRIAL_EXPIRED']
        
        if obj.event_type in payment_events:
            color = '#1E90FF'
        elif obj.event_type in subscription_events:
            color = '#32CD32'
        elif obj.event_type in invoice_events:
            color = '#FFA500'
        elif obj.event_type in webhook_events:
            color = '#9370DB'
        elif obj.event_type in trial_events:
            color = '#20B2AA'
        else:
            color = '#808080'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_event_type_display()
        )
    event_type_badge.short_description = 'Event Type'


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ['organization_link', 'method_type', 'display_info', 'is_default', 'is_active', 'created_at']
    list_filter = ['method_type', 'is_default', 'is_active', 'created_at']
    search_fields = ['organization__name', 'last_four_digits', 'bank_name', 'upi_id']
    readonly_fields = ['id', 'created_at', 'updated_at', 'metadata']
    ordering = ['-created_at']
    
    def organization_link(self, obj):
        url = reverse('admin:FinSyncOrganizations_organization_change', args=[obj.organization.id])
        return format_html('<a href="{}">{}</a>', url, obj.organization.name)
    organization_link.short_description = 'Organization'
    
    def display_info(self, obj):
        if obj.method_type == 'CARD':
            return f"{obj.card_network or 'Card'} •••• {obj.last_four_digits}"
        elif obj.method_type == 'UPI':
            return obj.upi_id
        elif obj.method_type == 'NETBANKING':
            return obj.bank_name
        return "-"
    display_info.short_description = 'Payment Info'


@admin.register(PaymentRetryLog)
class PaymentRetryLogAdmin(admin.ModelAdmin):
    list_display = ['payment_link', 'attempt_number', 'status_badge', 'next_retry_at', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['payment__razorpay_payment_id', 'failure_reason']
    readonly_fields = ['id', 'created_at']
    ordering = ['-created_at']
    
    def payment_link(self, obj):
        url = reverse('admin:FinSyncBilling_payment_change', args=[obj.payment.id])
        return format_html('<a href="{}">{}</a>', url, f"Payment {obj.payment.razorpay_payment_id or obj.payment.id}")
    payment_link.short_description = 'Payment'
    
    def status_badge(self, obj):
        colors = {
            'PENDING': '#FFA500',
            'PROCESSING': '#1E90FF',
            'COMPLETED': '#32CD32',
            'FAILED': '#DC143C',
        }
        color = colors.get(obj.status, '#808080')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.status
        )
    status_badge.short_description = 'Status'