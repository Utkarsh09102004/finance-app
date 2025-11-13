from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.db import transaction
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from decimal import Decimal
import logging

from FinSyncBilling.services import RazorpayService, BillingService
from FinSyncBilling.serializers import (
    SubscriptionPlanSerializer, PaymentSerializer, InvoiceSerializer,
    SubscriptionHistorySerializer, PaymentMethodSerializer, BillingOverviewSerializer,
    CheckoutSerializer, PlanChangeSerializer
)
from FinSyncBilling.models import Payment, Invoice, PaymentMethod, SubscriptionHistory
from FinSyncOrganizations.models import Organization, SubscriptionPlan
from FinSyncOrganizations.views import IsOrganizationMember, IsOrganizationOwner
from FinSyncBilling.permissions import CanViewBilling, CanManageBilling

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([AllowAny])
def pricing_plans(request):
    """Get all available subscription plans (public endpoint)"""
    try:
        plans = SubscriptionPlan.objects.filter(is_available=True).exclude(is_trial=True)
        
        # Add current pricing from settings
        plan_data = []
        for plan in plans:
            data = SubscriptionPlanSerializer(plan).data
            if plan.name in settings.SUBSCRIPTION_PRICING:
                data['price_monthly'] = str(settings.SUBSCRIPTION_PRICING[plan.name]['monthly'])
                data['features'] = {
                    'max_users': settings.SUBSCRIPTION_PRICING[plan.name]['max_users'],
                    'max_integrations': settings.SUBSCRIPTION_PRICING[plan.name]['max_integrations']
                }
            plan_data.append(data)
        
        return Response({
            'plans': plan_data,
            'currency': 'INR',
            'features_comparison': {
                'trial': {
                    'duration': '14 days',
                    'max_users': 1,
                    'max_integrations': 1,
                    'price': 'Free'
                },
                'individual': {
                    'max_users': 1,
                    'max_integrations': 3,
                    'support': 'Email support',
                    'price_monthly': str(settings.SUBSCRIPTION_PRICING.get('individual', {}).get('monthly', '299'))
                },
                'team': {
                    'max_users': 10,
                    'max_integrations': 5,
                    'support': 'Priority email support',
                    'price_monthly': str(settings.SUBSCRIPTION_PRICING.get('team', {}).get('monthly', '999'))
                }
            }
        })
    except Exception as e:
        logger.error(f"Error fetching pricing plans: {str(e)}")
        return Response(
            {'error': 'Failed to fetch pricing plans'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated, CanViewBilling])
def billing_overview(request):
    """Get billing overview for the current organization"""
    try:
        org = request.user.organization
        
        # Get recent payments
        recent_payments = Payment.objects.filter(
            organization=org
        ).order_by('-created_at')[:5]
        
        # Get recent invoices
        recent_invoices = Invoice.objects.filter(
            organization=org
        ).order_by('-created_at')[:5]
        
        # Get subscription history
        subscription_history = SubscriptionHistory.objects.filter(
            organization=org
        ).order_by('-created_at')[:10]
        
        # Calculate usage
        usage = {
            'users': {
                'current': org.get_active_user_count(),
                'limit': org.subscription_plan.max_users if org.subscription_plan else 0,
                'percentage': (org.get_active_user_count() / org.subscription_plan.max_users * 100) 
                    if org.subscription_plan and org.subscription_plan.max_users > 0 else 0
            },
            'integrations': {
                'current': org.get_active_integration_count(),
                'limit': org.subscription_plan.max_integrations if org.subscription_plan else 0,
                'percentage': (org.get_active_integration_count() / org.subscription_plan.max_integrations * 100)
                    if org.subscription_plan and org.subscription_plan.max_integrations > 0 else 0
            }
        }
        
        # Check if approaching limits
        approaching_limits = []
        if usage['users']['percentage'] >= 80:
            approaching_limits.append({
                'type': 'users',
                'message': f"You're using {usage['users']['current']} of {usage['users']['limit']} users"
            })
        if usage['integrations']['percentage'] >= 80:
            approaching_limits.append({
                'type': 'integrations',
                'message': f"You're using {usage['integrations']['current']} of {usage['integrations']['limit']} integrations"
            })
        
        # Prepare response
        data = {
            'organization': {
                'id': org.id,
                'name': org.name,
                'billing_email': org.billing_email or org.owner.email,
                'subscription_status': org.subscription_status,
                'subscription_plan': SubscriptionPlanSerializer(org.subscription_plan).data if org.subscription_plan else None,
                'trial_ends_at': org.trial_ends_at,
                'subscription_end_date': org.subscription_end_date,
                'payment_failed_count': org.payment_failed_count,
                'grace_period_ends_at': org.grace_period_ends_at
            },
            'usage': usage,
            'approaching_limits': approaching_limits,
            'recent_payments': PaymentSerializer(recent_payments, many=True).data,
            'recent_invoices': InvoiceSerializer(recent_invoices, many=True).data,
            'subscription_history': SubscriptionHistorySerializer(subscription_history, many=True).data,
            'can_upgrade': org.subscription_status in ['trialing', 'active'] and org.subscription_plan.name != 'team',
            'requires_payment_method': org.subscription_status == 'trialing' and not PaymentMethod.objects.filter(
                organization=org, is_active=True
            ).exists()
        }
        
        return Response(data)
        
    except Exception as e:
        logger.error(f"Error fetching billing overview: {str(e)}")
        return Response(
            {'error': 'Failed to fetch billing information'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated, CanManageBilling])
def create_checkout_session(request):
    """Create a checkout session for subscription purchase"""
    try:
        serializer = CheckoutSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        org = request.user.organization
        plan_name = serializer.validated_data['plan_name']
        
        # Get the plan
        plan = get_object_or_404(SubscriptionPlan, name=plan_name, is_available=True)
        
        # Check if organization can upgrade
        if org.subscription_plan and org.subscription_plan.name == 'team' and plan.name == 'individual':
            return Response(
                {'error': 'Cannot downgrade from team to individual plan with multiple users'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check user/integration limits for downgrade
        if org.subscription_plan and plan.max_users < org.get_active_user_count():
            return Response(
                {'error': f'Cannot change to this plan. You have {org.get_active_user_count()} users but the plan allows only {plan.max_users}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if org.subscription_plan and plan.max_integrations < org.get_active_integration_count():
            return Response(
                {'error': f'Cannot change to this plan. You have {org.get_active_integration_count()} integrations but the plan allows only {plan.max_integrations}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create Razorpay checkout
        razorpay_service = RazorpayService()
        print("hello1")
        if org.razorpay_subscription_id:
            # Update existing subscription
            is_downgrade = plan.price_monthly < org.subscription_plan.price_monthly
            subscription = razorpay_service.update_subscription(
                org, plan, schedule_change=is_downgrade
            )
            
            return Response({
                'action': 'subscription_updated',
                'subscription_id': subscription['id'],
                'scheduled': is_downgrade,
                'message': 'Subscription updated successfully' if not is_downgrade else 'Subscription will be downgraded at the end of the current billing cycle'
            })
        else:
            # Create subscription checkout for recurring payments
            try:
                subscription_checkout = razorpay_service.create_subscription_checkout(org, plan)
                
                return Response({
                    'action': 'subscription_checkout_created',
                    'checkout_url': subscription_checkout['short_url'],
                    'subscription_id': subscription_checkout['id'],
                    'amount': float(plan.price_monthly),
                    'currency': plan.currency,
                    'plan': SubscriptionPlanSerializer(plan).data,
                    'recurring': True
                })
            except Exception as e:
                logger.error(f"Failed to create subscription checkout: {str(e)}")
                # Fallback to payment link
                payment_link = razorpay_service.create_payment_link(org, plan)
                
                return Response({
                    'action': 'payment_link_created',
                    'payment_link': payment_link['short_url'],
                    'payment_link_id': payment_link['id'],
                    'amount': float(plan.price_monthly),
                    'currency': plan.currency,
                    'plan': SubscriptionPlanSerializer(plan).data,
                    'recurring': False
                })
            print("hello")
            logger.error(f"{payment_link}")
        
    except Exception as e:
        logger.error(f"Error creating checkout session: {str(e)}")
        return Response(
            {'error': 'Failed to create checkout session'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsOrganizationOwner])
def change_subscription_plan(request):
    """Change subscription plan (upgrade/downgrade)"""
    try:
        serializer = PlanChangeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        org = request.user.organization
        new_plan = serializer.validated_data['plan']
        schedule_at_cycle_end = serializer.validated_data.get('schedule_at_cycle_end', False)
        
        # Validation
        if not org.has_active_subscription:
            return Response(
                {'error': 'No active subscription found'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if org.subscription_plan == new_plan:
            return Response(
                {'error': 'Already on this plan'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check limits for downgrade
        if new_plan.max_users < org.get_active_user_count():
            return Response(
                {'error': f'Cannot downgrade. You have {org.get_active_user_count()} users but the plan allows only {new_plan.max_users}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if new_plan.max_integrations < org.get_active_integration_count():
            return Response(
                {'error': f'Cannot downgrade. You have {org.get_active_integration_count()} integrations but the plan allows only {new_plan.max_integrations}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Process plan change
        razorpay_service = RazorpayService()
        
        # Determine if it's an upgrade or downgrade
        is_downgrade = new_plan.price_monthly < org.subscription_plan.price_monthly
        
        # For downgrades, always schedule at cycle end
        if is_downgrade:
            schedule_at_cycle_end = True
        
        subscription = razorpay_service.update_subscription(
            org, new_plan, schedule_change=schedule_at_cycle_end
        )
        
        return Response({
            'success': True,
            'message': f"Plan {'downgrade' if is_downgrade else 'upgrade'} {'scheduled for end of billing cycle' if schedule_at_cycle_end else 'processed immediately'}",
            'subscription': subscription,
            'new_plan': SubscriptionPlanSerializer(new_plan).data
        })
        
    except Exception as e:
        logger.error(f"Error changing subscription plan: {str(e)}")
        return Response(
            {'error': 'Failed to change subscription plan'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsOrganizationOwner])
def cancel_subscription(request):
    """Cancel subscription"""
    try:
        org = request.user.organization
        
        if not org.razorpay_subscription_id:
            return Response(
                {'error': 'No active subscription found'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        cancel_immediately = request.data.get('cancel_immediately', False)
        
        razorpay_service = RazorpayService()
        subscription = razorpay_service.cancel_subscription(
            org, cancel_at_cycle_end=not cancel_immediately
        )
        
        return Response({
            'success': True,
            'message': 'Subscription cancelled' + (' immediately' if cancel_immediately else ' at end of billing cycle'),
            'subscription_end_date': org.subscription_end_date
        })
        
    except Exception as e:
        logger.error(f"Error cancelling subscription: {str(e)}")
        return Response(
            {'error': 'Failed to cancel subscription'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated, CanViewBilling])
def payment_methods(request):
    """Get saved payment methods"""
    try:
        org = request.user.organization
        methods = PaymentMethod.objects.filter(organization=org, is_active=True)
        
        return Response({
            'payment_methods': PaymentMethodSerializer(methods, many=True).data,
            'has_default': methods.filter(is_default=True).exists()
        })
        
    except Exception as e:
        logger.error(f"Error fetching payment methods: {str(e)}")
        return Response(
            {'error': 'Failed to fetch payment methods'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsOrganizationOwner])
def add_payment_method(request):
    """Add a new payment method"""
    try:
        org = request.user.organization
        token_id = request.data.get('token_id')
        set_as_default = request.data.get('set_as_default', True)
        
        if not token_id:
            return Response(
                {'error': 'Payment token is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create payment method record
        payment_method = PaymentMethod.objects.create(
            organization=org,
            razorpay_token_id=token_id,
            method_type=request.data.get('method_type', 'CARD'),
            last_four_digits=request.data.get('last_four_digits'),
            card_network=request.data.get('card_network'),
            bank_name=request.data.get('bank_name'),
            upi_id=request.data.get('upi_id'),
            is_default=set_as_default,
            metadata=request.data.get('metadata', {})
        )
        
        return Response({
            'success': True,
            'payment_method': PaymentMethodSerializer(payment_method).data
        })
        
    except Exception as e:
        logger.error(f"Error adding payment method: {str(e)}")
        return Response(
            {'error': 'Failed to add payment method'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsOrganizationOwner])
def remove_payment_method(request, method_id):
    """Remove a payment method"""
    try:
        org = request.user.organization
        payment_method = get_object_or_404(
            PaymentMethod, 
            id=method_id, 
            organization=org
        )
        
        # Don't allow removing the last payment method if there's an active subscription
        if payment_method.is_default and org.has_active_subscription:
            other_methods = PaymentMethod.objects.filter(
                organization=org, 
                is_active=True
            ).exclude(id=method_id)
            
            if not other_methods.exists():
                return Response(
                    {'error': 'Cannot remove the last payment method while subscription is active'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        payment_method.is_active = False
        payment_method.save()
        
        return Response({'success': True})
        
    except Exception as e:
        logger.error(f"Error removing payment method: {str(e)}")
        return Response(
            {'error': 'Failed to remove payment method'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated, CanViewBilling])
def invoices(request):
    """Get all invoices for the organization"""
    try:
        org = request.user.organization
        invoices = Invoice.objects.filter(organization=org).order_by('-created_at')
        
        # Pagination
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        start = (page - 1) * per_page
        end = start + per_page
        
        total = invoices.count()
        invoices = invoices[start:end]
        
        return Response({
            'invoices': InvoiceSerializer(invoices, many=True).data,
            'pagination': {
                'total': total,
                'page': page,
                'per_page': per_page,
                'pages': (total + per_page - 1) // per_page
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching invoices: {str(e)}")
        return Response(
            {'error': 'Failed to fetch invoices'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated, CanViewBilling])
def download_invoice(request, invoice_id):
    """Download invoice PDF"""
    try:
        org = request.user.organization
        invoice = get_object_or_404(Invoice, id=invoice_id, organization=org)
        
        # TODO: Generate PDF invoice
        # For now, return invoice data
        return Response({
            'invoice': InvoiceSerializer(invoice).data,
            'download_url': invoice.invoice_url if invoice.invoice_url else None
        })
        
    except Exception as e:
        logger.error(f"Error downloading invoice: {str(e)}")
        return Response(
            {'error': 'Failed to download invoice'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsOrganizationOwner])
def update_billing_info(request):
    """Update billing contact information"""
    try:
        org = request.user.organization
        
        # Update billing info
        org.billing_email = request.data.get('billing_email', org.billing_email)
        org.billing_name = request.data.get('billing_name', org.billing_name)
        org.billing_phone = request.data.get('billing_phone', org.billing_phone)
        org.save()
        
        # Update in Razorpay if customer exists
        if org.razorpay_customer_id:
            razorpay_service = RazorpayService()
            try:
                razorpay_service.client.customer.edit(
                    org.razorpay_customer_id,
                    {
                        "name": org.billing_name or org.name,
                        "email": org.billing_email or org.owner.email,
                        "contact": org.billing_phone or ""
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to update Razorpay customer: {str(e)}")
        
        return Response({
            'success': True,
            'billing_info': {
                'billing_email': org.billing_email,
                'billing_name': org.billing_name,
                'billing_phone': org.billing_phone
            }
        })
        
    except Exception as e:
        logger.error(f"Error updating billing info: {str(e)}")
        return Response(
            {'error': 'Failed to update billing information'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_payment(request):
    """Verify payment or subscription after Razorpay redirect"""
    try:
        payment_id = request.data.get('payment_id')
        payment_link_id = request.data.get('payment_link_id')
        subscription_id = request.data.get('subscription_id')
        
        # For subscriptions, we need subscription_id
        # For one-time payments, we need payment_id
        if not payment_id and not subscription_id:
            return Response(
                {'success': False, 'error': 'Payment ID or Subscription ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        org = request.user.organization
        razorpay_service = RazorpayService()
        
        # Handle subscription verification
        if subscription_id:
            # Check if subscription already processed
            if org.razorpay_subscription_id == subscription_id and org.subscription_status == Organization.SubscriptionStatus.ACTIVE:
                return Response({
                    'success': True,
                    'message': 'Subscription already verified',
                    'subscription_status': org.subscription_status,
                    'already_processed': True
                })
            
            try:
                subscription = razorpay_service.client.subscription.fetch(subscription_id)
            except Exception as e:
                logger.error(f"Razorpay subscription API error: {str(e)}")
                return Response(
                    {'success': False, 'error': 'Failed to fetch subscription details from Razorpay'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            if subscription['status'] == 'active':
                # Extract plan name from subscription notes
                plan_name = subscription.get('notes', {}).get('plan_name')
                if not plan_name:
                    logger.error(f"No plan_name in subscription notes for subscription {subscription_id}")
                    return Response(
                        {'success': False, 'error': 'Invalid subscription data: missing plan information'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                try:
                    plan = SubscriptionPlan.objects.get(name=plan_name)
                except SubscriptionPlan.DoesNotExist:
                    logger.error(f"Invalid plan name in subscription: {plan_name}")
                    return Response(
                        {'success': False, 'error': 'Invalid subscription plan'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Use transaction to ensure atomicity
                with transaction.atomic():
                    # Update organization subscription
                    org.razorpay_subscription_id = subscription_id
                    org.subscription_status = Organization.SubscriptionStatus.ACTIVE
                    org.subscription_plan = plan
                    org.subscription_start_date = timezone.now().date()
                    org.trial_ends_at = None
                    org.payment_failed_count = 0
                    org.grace_period_ends_at = None
                    org.save()
                    
                    # Create subscription history entry
                    SubscriptionHistory.objects.create(
                        organization=org,
                        action='CREATED',
                        to_plan=plan,
                        razorpay_subscription_id=subscription_id,
                        performed_by=request.user,
                        reason='Subscription verified after redirect'
                    )
                
                logger.info(f"Subscription verified successfully for org {org.id}, subscription {subscription_id}")
                
                return Response({
                    'success': True,
                    'message': 'Subscription verified successfully',
                    'subscription_status': org.subscription_status,
                    'subscription_plan': SubscriptionPlanSerializer(org.subscription_plan).data,
                    'subscription_type': 'recurring'
                })
            else:
                logger.warning(f"Subscription {subscription_id} status is {subscription['status']}, not active")
                return Response({
                    'success': False,
                    'error': f'Subscription not active. Status: {subscription["status"]}',
                    'subscription_status': subscription['status']
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Handle one-time payment verification (existing logic)
        if payment_id:
            # Check if payment already processed (idempotency)
            existing_payment = Payment.objects.filter(
                razorpay_payment_id=payment_id,
                status='COMPLETED'
            ).first()
            
            if existing_payment:
                return Response({
                    'success': True,
                    'message': 'Payment already verified',
                    'subscription_status': org.subscription_status,
                    'already_processed': True
                })
            
            # Verify with Razorpay
            try:
                payment = razorpay_service.client.payment.fetch(payment_id)
            except Exception as e:
                logger.error(f"Razorpay API error: {str(e)}")
                return Response(
                    {'success': False, 'error': 'Failed to fetch payment details from Razorpay'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            if payment['status'] == 'captured':
                # Extract plan name from payment notes
                plan_name = payment.get('notes', {}).get('plan_name')
                if not plan_name:
                    logger.error(f"No plan_name in payment notes for payment {payment_id}")
                    return Response(
                        {'success': False, 'error': 'Invalid payment data: missing plan information'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                try:
                    plan = SubscriptionPlan.objects.get(name=plan_name)
                except SubscriptionPlan.DoesNotExist:
                    logger.error(f"Invalid plan name in payment: {plan_name}")
                    return Response(
                        {'success': False, 'error': 'Invalid subscription plan'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Use transaction to ensure atomicity
                with transaction.atomic():
                    # Create payment record
                    payment_record = Payment.objects.create(
                        organization=org,
                        razorpay_payment_id=payment_id,
                        amount=Decimal(payment['amount']) / 100,  # Convert from paise to rupees
                        currency=payment['currency'],
                        status='COMPLETED',
                        payment_method=payment.get('method', 'UNKNOWN').upper(),
                        paid_at=timezone.now(),
                        metadata={
                            **payment,
                            'payment_link_id': payment_link_id  # Store in metadata
                        }
                    )
                    
                    # Update organization subscription
                    org.subscription_status = Organization.SubscriptionStatus.ACTIVE
                    org.subscription_plan = plan
                    org.subscription_start_date = timezone.now().date()
                    org.trial_ends_at = None
                    org.payment_failed_count = 0  # Reset failed payment count
                    org.grace_period_ends_at = None
                    org.save()
                    
                    # Create subscription history entry
                    SubscriptionHistory.objects.create(
                        organization=org,
                        action='CREATED',
                        to_plan=plan,
                        performed_by=request.user,
                        reason='Payment verified after redirect'
                    )
                    
                    # Generate invoice
                    billing_service = BillingService()
                    invoice = billing_service.generate_invoice(org, payment_record)
                
                logger.info(f"Payment verified successfully for org {org.id}, payment {payment_id}")
                
                return Response({
                    'success': True,
                    'message': 'Payment verified successfully',
                    'subscription_status': org.subscription_status,
                    'subscription_plan': SubscriptionPlanSerializer(org.subscription_plan).data,
                    'invoice_id': invoice.invoice_number if invoice else None,
                    'subscription_type': 'one_time'
                })
            else:
                # Payment not captured
                logger.warning(f"Payment {payment_id} status is {payment['status']}, not captured")
                return Response({
                    'success': False,
                    'error': f'Payment not completed. Status: {payment["status"]}',
                    'payment_status': payment['status']
                }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Error verifying payment: {str(e)}", exc_info=True)
        return Response(
            {'success': False, 'error': 'Failed to verify payment'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )