import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import useCustomSnackbar from '../hooks/useNotifier';
import { billingAPI } from '../api/billing';
import { useAuth } from '../contexts/AuthContext';
import { Loader2, CreditCard, Check, ExternalLink } from 'lucide-react';

export default function Checkout() {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { showSuccessToast, showErrorToast } = useCustomSnackbar();
  const { user } = useAuth();
  
  const planName = searchParams.get('plan');

  useEffect(() => {
    // Ensure user is authenticated
    if (!user) {
      navigate('/login?redirect=/checkout?plan=' + planName);
      return;
    }
  }, [user, navigate, planName]);

  const handleCheckout = async () => {
    if (!planName) {
      showErrorToast('No plan selected');
      return;
    }

    setLoading(true);
    try {
      const response = await billingAPI.createCheckout(planName);

      if (response.action === 'payment_link_created' && response.payment_link) {
        // Redirect to Razorpay payment page (one-time payment)
        window.location.href = response.payment_link;
      } else if (response.action === 'subscription_checkout_created' && response.checkout_url) {
        // Redirect to Razorpay subscription checkout (recurring payment)
        window.location.href = response.checkout_url;
      } else if (response.action === 'subscription_updated') {
        // Subscription was updated (upgrade/downgrade)
        showSuccessToast(response.message || 'Subscription updated successfully');
        
        // Redirect to billing page after a short delay
        setTimeout(() => {
          navigate('/settings/billing');
        }, 2000);
      }
    } catch (error) {
      console.error('Checkout error:', error);
      showErrorToast(error.response?.data?.error || 'Failed to process checkout');
    } finally {
      setLoading(false);
    }
  };

  const getPlanDetails = (plan) => {
    const plans = {
      individual: {
        name: 'Individual Plan',
        price: '₹299',
        period: 'per month',
        features: [
          '1 user',
          '3 integrations',
          'Email support',
          'API access',
          'Data export',
        ],
      },
      team: {
        name: 'Team Plan',
        price: '₹999',
        period: 'per month',
        features: [
          'Up to 10 users',
          '5 integrations',
          'Priority email support',
          'API access',
          'Data export',
          'Advanced analytics',
        ],
      },
    };

    return plans[plan] || null;
  };

  const planDetails = planName ? getPlanDetails(planName) : null;

  if (!planDetails) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Invalid Plan</CardTitle>
            <CardDescription>The selected plan is not valid.</CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => navigate('/pricing')} className="w-full">
              Back to Pricing
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-12">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid md:grid-cols-2 gap-8">
          {/* Order Summary */}
          <Card>
            <CardHeader>
              <CardTitle>Order Summary</CardTitle>
              <CardDescription>Review your subscription details</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div>
                  <h3 className="font-semibold text-lg">{planDetails.name}</h3>
                  <p className="text-3xl font-bold mt-2">
                    {planDetails.price}
                    <span className="text-sm font-normal text-gray-600 ml-2">
                      {planDetails.period}
                    </span>
                  </p>
                </div>

                <div className="border-t pt-4">
                  <h4 className="font-medium mb-3">Included features:</h4>
                  <ul className="space-y-2">
                    {planDetails.features.map((feature, index) => (
                      <li key={index} className="flex items-start">
                        <Check className="h-5 w-5 text-green-500 mr-2 flex-shrink-0" />
                        <span className="text-gray-700">{feature}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="border-t pt-4">
                  <div className="flex justify-between">
                    <span className="font-medium">Subtotal</span>
                    <span>{planDetails.price}</span>
                  </div>
                  <div className="flex justify-between text-sm text-gray-600 mt-1">
                    <span>GST (18%)</span>
                    <span>Calculated at checkout</span>
                  </div>
                  <div className="flex justify-between font-bold text-lg mt-4 pt-4 border-t">
                    <span>Total</span>
                    <span>{planDetails.price}*</span>
                  </div>
                  <p className="text-xs text-gray-500 mt-2">
                    *Final amount including taxes will be shown on the payment page
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Payment Details */}
          <Card>
            <CardHeader>
              <CardTitle>Payment Details</CardTitle>
              <CardDescription>Complete your subscription purchase</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="bg-blue-50 p-4 rounded-lg">
                  <div className="flex items-start space-x-2">
                    <ExternalLink className="h-4 w-4 text-blue-900 mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="text-sm text-blue-900 font-medium">Secure Recurring Payment via Razorpay</p>
                      <p className="text-sm text-blue-800 mt-1">
                        You'll be redirected to set up automatic monthly payments. 
                        We accept credit/debit cards, UPI, net banking, and digital wallets.
                      </p>
                    </div>
                  </div>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center space-x-2 text-sm text-gray-600">
                    <CreditCard className="h-4 w-4" />
                    <span>Secure payment powered by Razorpay</span>
                  </div>
                  <div className="flex items-center space-x-2 text-sm text-gray-600">
                    <Check className="h-4 w-4" />
                    <span>Automatic monthly payments</span>
                  </div>
                  <div className="flex items-center space-x-2 text-sm text-gray-600">
                    <Check className="h-4 w-4" />
                    <span>Cancel anytime, no questions asked</span>
                  </div>
                  <div className="flex items-center space-x-2 text-sm text-gray-600">
                    <Check className="h-4 w-4" />
                    <span>Instant access after payment</span>
                  </div>
                </div>

                <Button
                  className="w-full"
                  size="lg"
                  onClick={handleCheckout}
                  disabled={loading}
                >
                  {loading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Redirecting to payment...
                    </>
                  ) : (
                    <>
                      Proceed to Payment
                      <ExternalLink className="ml-2 h-4 w-4" />
                    </>
                  )}
                </Button>

                <p className="text-xs text-center text-gray-500">
                  By proceeding, you agree to our Terms of Service and Privacy Policy
                </p>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Back to pricing link */}
        <div className="mt-8 text-center">
          <Button
            variant="link"
            onClick={() => navigate('/pricing')}
            className="text-gray-600"
          >
            ← Back to pricing
          </Button>
        </div>
      </div>
    </div>
  );
}