from django.urls import path
from FinSyncBilling import views
from FinSyncBilling.webhooks import razorpay_webhook

app_name = 'billing'

urlpatterns = [
    # Public endpoints
    path('pricing/', views.pricing_plans, name='pricing-plans'),
    
    # Authenticated endpoints
    path('overview/', views.billing_overview, name='billing-overview'),
    path('checkout/', views.create_checkout_session, name='create-checkout'),
    path('subscription/change/', views.change_subscription_plan, name='change-plan'),
    path('subscription/cancel/', views.cancel_subscription, name='cancel-subscription'),
    
    # Payment methods
    path('payment-methods/', views.payment_methods, name='payment-methods'),
    path('payment-methods/add/', views.add_payment_method, name='add-payment-method'),
    path('payment-methods/<uuid:method_id>/remove/', views.remove_payment_method, name='remove-payment-method'),
    
    # Invoices
    path('invoices/', views.invoices, name='invoices'),
    path('invoices/<uuid:invoice_id>/download/', views.download_invoice, name='download-invoice'),
    
    # Billing info
    path('billing-info/update/', views.update_billing_info, name='update-billing-info'),
    
    # Payment verification
    path('verify-payment/', views.verify_payment, name='verify-payment'),
    
    # Webhooks
    path('webhooks/razorpay/', razorpay_webhook, name='razorpay-webhook'),
]