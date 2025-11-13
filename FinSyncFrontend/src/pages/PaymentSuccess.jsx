import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { CheckCircle, ArrowRight, Sparkles, Loader2, AlertCircle } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { billingAPI } from '../api/billing';
import useCustomSnackbar from '../hooks/useNotifier';

export default function PaymentSuccess() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { user } = useAuth();
  const [countdown, setCountdown] = useState(5);
  const [verifying, setVerifying] = useState(true);
  const [verificationError, setVerificationError] = useState(null);
  const { showSuccessToast, showErrorToast } = useCustomSnackbar();

  // Get payment details from URL params (if passed by Razorpay)
  const paymentId = searchParams.get('razorpay_payment_id');
  const paymentLinkId = searchParams.get('razorpay_payment_link_id');
  const paymentLinkRefId = searchParams.get('razorpay_payment_link_reference_id');
  const paymentLinkStatus = searchParams.get('razorpay_payment_link_status');
  const signature = searchParams.get('razorpay_signature');
  
  // Get subscription details (for recurring payments)
  const subscriptionId = searchParams.get('razorpay_subscription_id');
  const subscriptionStatus = searchParams.get('razorpay_subscription_status');

  useEffect(() => {
    // Verify payment or subscription on component mount
    if (paymentId || paymentLinkId || subscriptionId) {
      verifyPayment();
    } else {
      setVerifying(false);
      setVerificationError('No payment or subscription information found');
    }
  }, [paymentId, paymentLinkId, subscriptionId]);

  useEffect(() => {
    // Auto-redirect to dashboard after countdown (only if verification succeeded)
    if (!verifying && !verificationError) {
      const timer = setInterval(() => {
        setCountdown(prev => {
          if (prev <= 1) {
            navigate('/dashboard');
            return 0;
          }
          return prev - 1;
        });
      }, 1000);

      return () => clearInterval(timer);
    }
  }, [navigate, verifying, verificationError]);

  const verifyPayment = async () => {
    try {
      const verificationData = {
        payment_id: paymentId,
        payment_link_id: paymentLinkId,
        payment_link_reference_id: paymentLinkRefId,
        payment_link_status: paymentLinkStatus,
        signature: signature,
        subscription_id: subscriptionId,
        subscription_status: subscriptionStatus
      };

      const response = await billingAPI.verifyPayment(verificationData);

      if (response.success) {
        const successMessage = response.subscription_type === 'recurring' 
          ? 'Subscription verified successfully!' 
          : 'Payment verified successfully!';
        showSuccessToast(successMessage);
        setVerifying(false);
      } else {
        throw new Error(response.error || 'Payment verification failed');
      }
    } catch (error) {
      console.error('Payment verification error:', error);
      setVerificationError(error.response?.data?.error || error.message);
      showErrorToast('Payment verification failed. Please contact support.');
      setVerifying(false);
    }
  };

  if (verifying) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
        <Card className="w-full max-w-lg">
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Loader2 className="h-12 w-12 animate-spin text-blue-600 mb-4" />
            <p className="text-lg text-gray-600">Verifying your payment...</p>
            <p className="text-sm text-gray-500 mt-2">Please wait while we confirm your subscription</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (verificationError) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
        <Card className="w-full max-w-lg">
          <CardHeader className="text-center">
            <div className="mx-auto mb-4 relative">
              <div className="absolute inset-0 bg-amber-500/20 rounded-full blur-xl animate-pulse"></div>
              <AlertCircle className="h-16 w-16 text-amber-500 relative" />
            </div>
            <CardTitle className="text-2xl">Payment Verification Issue</CardTitle>
            <CardDescription>
              {verificationError}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="bg-amber-50 p-4 rounded-lg">
              <p className="text-sm text-amber-900">
                Don't worry! If your payment was successful, it will be automatically verified through our system shortly.
              </p>
            </div>
            <div className="space-y-3">
              <Button 
                className="w-full" 
                size="lg"
                onClick={() => navigate('/settings')}
              >
                Go to Settings
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
              <p className="text-center text-sm text-gray-500">
                Check your subscription status in the billing section
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <Card className="w-full max-w-lg">
        <CardHeader className="text-center">
          <div className="mx-auto mb-4 relative">
            <div className="absolute inset-0 bg-green-500/20 rounded-full blur-xl animate-pulse"></div>
            <CheckCircle className="h-16 w-16 text-green-500 relative" />
          </div>
          <CardTitle className="text-2xl">Payment Successful!</CardTitle>
          <CardDescription>
            Welcome to FinSync {user?.first_name || ''}! Your subscription is now active.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="bg-green-50 p-4 rounded-lg">
            <div className="flex items-start space-x-3">
              <Sparkles className="h-5 w-5 text-green-600 mt-0.5" />
              <div className="text-sm">
                <p className="font-medium text-green-900">What's next?</p>
                <ul className="mt-2 space-y-1 text-green-800">
                  <li>• Connect your accounting software</li>
                  <li>• Start asking financial questions</li>
                  <li>• Invite your team members</li>
                </ul>
              </div>
            </div>
          </div>

          {(paymentId || subscriptionId) && (
            <div className="text-sm text-gray-600 bg-gray-50 p-3 rounded">
              <p className="font-medium">
                {subscriptionId ? 'Subscription Reference' : 'Payment Reference'}
              </p>
              <p className="font-mono text-xs mt-1">{subscriptionId || paymentId}</p>
            </div>
          )}

          <div className="space-y-3">
            <Button 
              className="w-full" 
              size="lg"
              onClick={() => navigate('/dashboard')}
            >
              Go to Dashboard
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
            
            <p className="text-center text-sm text-gray-500">
              Redirecting in {countdown} seconds...
            </p>
          </div>

          <div className="border-t pt-4">
            <p className="text-xs text-center text-gray-500">
              A confirmation email has been sent to your registered email address.
              Need help? Contact support@finsync.com
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}