# FinSyncOrganizations/admin.py
from django.contrib import admin
from .models import SubscriptionPlan, Organization, OrganizationMembershipLog, OrganizationInvite

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_name', 'max_users', 'max_integrations', 'is_trial', 'trial_duration_days', 'is_available', 'price_monthly')
    list_filter = ('is_trial', 'is_available')
    search_fields = ('name', 'display_name')
    ordering = ('name',)

@admin.register(Organization)
# admin.site.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'domain', 'subscription_plan', 'subscription_status', 'get_member_count', 'trial_ends_at', 'is_active', 'created_at', 'updated_at', 'created_by', 'owner')
    list_filter = ('subscription_status', 'subscription_plan', 'is_active')
    search_fields = ('name', 'domain')
    ordering = ('name',)
    readonly_fields = ('created_at', 'updated_at', 'created_by') # Make these read-only
    fieldsets = (
        ('Organization Info', {'fields': ('name', 'domain', 'is_active', 'created_by', 'owner')}),
        ('Subscription', {'fields': ('subscription_plan', 'subscription_status', 'trial_ends_at', 'subscription_start_date', 'subscription_end_date')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
        # ('Payment Provider', {'fields': ('stripe_customer_id', 'stripe_subscription_id')}) # If using Stripe
    )

    def get_member_count(self, obj):
        return obj.get_active_user_count()
    get_member_count.short_description = 'Active Members'


admin.site.register(OrganizationMembershipLog)


admin.site.register(OrganizationInvite)