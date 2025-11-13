import React from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { XCircle, RefreshCw, ArrowLeft, AlertCircle } from 'lucide-react';

export default function PaymentFailure() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  // Get error details from URL params
  const errorCode = searchParams.get('error_code');
  const errorDescription = searchParams.get('error_description');
  const errorReason = searchParams.get('error_reason');

  const getErrorMessage = () => {
    if (errorDescription) return errorDescription;
    if (errorReason) return errorReason;
    
    switch (errorCode) {
      case 'PAYMENT_CANCELLED':
        return 'You cancelled the payment. No charges were made.';
      case 'PAYMENT_FAILED':
        return 'The payment could not be processed. Please try again.';
      case 'PAYMENT_TIMEOUT':
        return 'The payment session timed out. Please try again.';
      default:
        return 'Something went wrong with the payment. Please try again or contact support.';
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <Card className="w-full max-w-lg">
        <CardHeader className="text-center">
          <div className="mx-auto mb-4 relative">
            <div className="absolute inset-0 bg-red-500/20 rounded-full blur-xl animate-pulse"></div>
            <XCircle className="h-16 w-16 text-red-500 relative" />
          </div>
          <CardTitle className="text-2xl">Payment Failed</CardTitle>
          <CardDescription>
            {getErrorMessage()}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="bg-amber-50 p-4 rounded-lg">
            <div className="flex items-start space-x-3">
              <AlertCircle className="h-5 w-5 text-amber-600 mt-0.5" />
              <div className="text-sm">
                <p className="font-medium text-amber-900">What can you do?</p>
                <ul className="mt-2 space-y-1 text-amber-800">
                  <li>• Check your payment details and try again</li>
                  <li>• Try a different payment method</li>
                  <li>• Contact your bank if the issue persists</li>
                  <li>• Reach out to our support team</li>
                </ul>
              </div>
            </div>
          </div>

          {errorCode && (
            <div className="text-sm text-gray-600 bg-gray-50 p-3 rounded">
              <p className="font-medium">Error Reference</p>
              <p className="font-mono text-xs mt-1">{errorCode}</p>
            </div>
          )}

          <div className="space-y-3">
            <Button 
              className="w-full" 
              size="lg"
              onClick={() => navigate('/pricing')}
            >
              <RefreshCw className="mr-2 h-4 w-4" />
              Try Again
            </Button>
            
            <Button 
              variant="outline"
              className="w-full" 
              size="lg"
              onClick={() => navigate('/dashboard')}
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Dashboard
            </Button>
          </div>

          <div className="border-t pt-4">
            <p className="text-xs text-center text-gray-500">
              No charges were made to your account. 
              Need help? Contact support@finsync.com
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}