from rest_framework import serializers
from FinSyncBilling.models import (
    Payment, Invoice, SubscriptionHistory, BillingEvent, PaymentMethod
)
from FinSyncOrganizations.models import SubscriptionPlan, Organization
from FinSyncAuth.serializers import UserSerializer


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = [
            'name', 'display_name', 'max_users', 'max_integrations',
            'price_monthly', 'currency', 'features', 'is_trial',
            'trial_duration_days'
        ]


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            'id', 'razorpay_payment_id', 'amount', 'currency', 'status',
            'payment_method', 'description', 'failure_reason', 'paid_at',
            'created_at'
        ]


class InvoiceSerializer(serializers.ModelSerializer):
    subscription_plan = SubscriptionPlanSerializer(read_only=True)
    payment = PaymentSerializer(read_only=True)
    
    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'amount', 'tax_amount', 'total_amount',
            'currency', 'status', 'billing_period_start', 'billing_period_end',
            'due_date', 'paid_at', 'subscription_plan', 'payment',
            'invoice_url', 'created_at'
        ]


class SubscriptionHistorySerializer(serializers.ModelSerializer):
    from_plan = SubscriptionPlanSerializer(read_only=True)
    to_plan = SubscriptionPlanSerializer(read_only=True)
    performed_by = UserSerializer(read_only=True)
    
    class Meta:
        model = SubscriptionHistory
        fields = [
            'id', 'action', 'from_plan', 'to_plan', 'performed_by',
            'reason', 'created_at'
        ]


class PaymentMethodSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    
    class Meta:
        model = PaymentMethod
        fields = [
            'id', 'method_type', 'last_four_digits', 'card_network',
            'bank_name', 'upi_id', 'is_default', 'expires_at',
            'display_name', 'created_at'
        ]
    
    def get_display_name(self, obj):
        if obj.method_type == 'CARD':
            return f"{obj.card_network or 'Card'} ending in {obj.last_four_digits}"
        elif obj.method_type == 'UPI':
            return f"UPI - {obj.upi_id}"
        elif obj.method_type == 'NETBANKING':
            return f"Net Banking - {obj.bank_name}"
        return obj.method_type


class BillingEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingEvent
        fields = [
            'id', 'event_type', 'description', 'created_at'
        ]


class BillingOverviewSerializer(serializers.Serializer):
    organization = serializers.SerializerMethodField()
    current_plan = SubscriptionPlanSerializer(source='subscription_plan', read_only=True)
    usage = serializers.SerializerMethodField()
    recent_payments = PaymentSerializer(many=True, read_only=True)
    recent_invoices = InvoiceSerializer(many=True, read_only=True)
    payment_methods = PaymentMethodSerializer(many=True, read_only=True)
    
    def get_organization(self, obj):
        return {
            'id': obj.id,
            'name': obj.name,
            'subscription_status': obj.subscription_status,
            'trial_ends_at': obj.trial_ends_at,
            'subscription_end_date': obj.subscription_end_date,
            'billing_email': obj.billing_email or obj.owner.email
        }
    
    def get_usage(self, obj):
        return {
            'users': {
                'current': obj.get_active_user_count(),
                'limit': obj.subscription_plan.max_users if obj.subscription_plan else 0
            },
            'integrations': {
                'current': obj.get_active_integration_count(),
                'limit': obj.subscription_plan.max_integrations if obj.subscription_plan else 0
            }
        }


class CheckoutSerializer(serializers.Serializer):
    plan_name = serializers.ChoiceField(
        choices=['individual', 'team'],
        required=True
    )
    payment_method_id = serializers.CharField(required=False)
    
    def validate_plan_name(self, value):
        try:
            SubscriptionPlan.objects.get(name=value, is_available=True)
        except SubscriptionPlan.DoesNotExist:
            raise serializers.ValidationError("Invalid plan selected")
        return value


class PlanChangeSerializer(serializers.Serializer):
    plan_name = serializers.ChoiceField(
        choices=['individual', 'team'],
        required=True
    )
    schedule_at_cycle_end = serializers.BooleanField(default=False)
    
    def validate_plan_name(self, value):
        try:
            self.plan = SubscriptionPlan.objects.get(name=value, is_available=True)
        except SubscriptionPlan.DoesNotExist:
            raise serializers.ValidationError("Invalid plan selected")
        return value
    
    def validate(self, data):
        data['plan'] = self.plan
        return data