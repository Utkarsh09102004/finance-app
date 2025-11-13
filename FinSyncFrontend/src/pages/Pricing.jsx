import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Check, X, Loader2 } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import useCustomSnackbar from '../hooks/useNotifier';
import { billingAPI } from '../api/billing';
import { useAuth } from '../contexts/AuthContext';

export default function Pricing() {
  const [pricingData, setPricingData] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const { showErrorToast } = useCustomSnackbar();
  const { user } = useAuth();

  useEffect(() => {
    fetchPricingData();
  }, []);

  const fetchPricingData = async () => {
    try {
      const data = await billingAPI.getPricingPlans();
      setPricingData(data);
    } catch (error) {
      console.error('Failed to fetch pricing data:', error);
      showErrorToast('Failed to load pricing information');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectPlan = (planName) => {
    if (user) {
      // User is logged in, redirect to checkout
      navigate(`/checkout?plan=${planName}`);
    } else {
      // User is not logged in, redirect to signup with plan
      navigate(`/signup?plan=${planName}`);
    }
  };

  const allFeatures = [
    { key: 'users', label: 'Team Members' },
    { key: 'integrations', label: 'Integrations' },
    { key: 'support', label: 'Support' },
    { key: 'api_access', label: 'API Access' },
    { key: 'data_export', label: 'Data Export' },
    { key: 'analytics', label: 'Advanced Analytics' },
  ];

  const planFeatures = {
    trial: {
      users: '1 user',
      integrations: '1 integration',
      support: 'Community support',
      api_access: false,
      data_export: false,
      analytics: false,
    },
    individual: {
      users: '1 user',
      integrations: '3 integrations',
      support: 'Email support',
      api_access: true,
      data_export: true,
      analytics: false,
    },
    team: {
      users: 'Up to 10 users',
      integrations: '5 integrations',
      support: 'Priority email support',
      api_access: true,
      data_export: true,
      analytics: true,
    },
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-12">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="text-center">
          <h1 className="text-4xl font-bold text-gray-900 sm:text-5xl">
            Simple, transparent pricing
          </h1>
          <p className="mt-4 text-xl text-gray-600">
            Choose the plan that fits your needs. Start with a 14-day free trial.
          </p>
        </div>

        {/* Pricing Cards */}
        <div className="mt-12 grid gap-8 lg:grid-cols-3">
          {/* Trial Plan */}
          <Card className="relative border-gray-200">
            <CardHeader>
              <CardTitle className="text-2xl">Trial</CardTitle>
              <CardDescription>Perfect for getting started</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="mb-6">
                <span className="text-4xl font-bold">Free</span>
                <span className="text-gray-600 ml-2">for 14 days</span>
              </div>
              <ul className="space-y-3">
                {allFeatures.map((feature) => (
                  <li key={feature.key} className="flex items-start">
                    {planFeatures.trial[feature.key] ? (
                      <>
                        <Check className="h-5 w-5 text-green-500 mr-2 flex-shrink-0" />
                        <span className="text-gray-700">
                          {typeof planFeatures.trial[feature.key] === 'string'
                            ? planFeatures.trial[feature.key]
                            : feature.label}
                        </span>
                      </>
                    ) : (
                      <>
                        <X className="h-5 w-5 text-gray-300 mr-2 flex-shrink-0" />
                        <span className="text-gray-400">{feature.label}</span>
                      </>
                    )}
                  </li>
                ))}
              </ul>
            </CardContent>
            <CardFooter>
              <Button
                className="w-full"
                variant="outline"
                onClick={() => handleSelectPlan('trial')}
              >
                Start Free Trial
              </Button>
            </CardFooter>
          </Card>

          {/* Individual Plan */}
          <Card className="relative border-blue-600 shadow-lg">
            <div className="absolute -top-4 left-0 right-0 flex justify-center">
              <Badge className="bg-blue-600 text-white">Most Popular</Badge>
            </div>
            <CardHeader>
              <CardTitle className="text-2xl">Individual</CardTitle>
              <CardDescription>For solo professionals</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="mb-6">
                <span className="text-4xl font-bold">
                  ₹{pricingData?.features_comparison.individual.price_monthly || '299'}
                </span>
                <span className="text-gray-600 ml-2">/month</span>
              </div>
              <ul className="space-y-3">
                {allFeatures.map((feature) => (
                  <li key={feature.key} className="flex items-start">
                    {planFeatures.individual[feature.key] ? (
                      <>
                        <Check className="h-5 w-5 text-green-500 mr-2 flex-shrink-0" />
                        <span className="text-gray-700">
                          {typeof planFeatures.individual[feature.key] === 'string'
                            ? planFeatures.individual[feature.key]
                            : feature.label}
                        </span>
                      </>
                    ) : (
                      <>
                        <X className="h-5 w-5 text-gray-300 mr-2 flex-shrink-0" />
                        <span className="text-gray-400">{feature.label}</span>
                      </>
                    )}
                  </li>
                ))}
              </ul>
            </CardContent>
            <CardFooter>
              <Button
                className="w-full bg-blue-600 hover:bg-blue-700"
                onClick={() => handleSelectPlan('individual')}
              >
                Get Started
              </Button>
            </CardFooter>
          </Card>

          {/* Team Plan */}
          <Card className="relative border-gray-200">
            <CardHeader>
              <CardTitle className="text-2xl">Team</CardTitle>
              <CardDescription>For growing teams</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="mb-6">
                <span className="text-4xl font-bold">
                  ₹{pricingData?.features_comparison.team.price_monthly || '999'}
                </span>
                <span className="text-gray-600 ml-2">/month</span>
              </div>
              <ul className="space-y-3">
                {allFeatures.map((feature) => (
                  <li key={feature.key} className="flex items-start">
                    {planFeatures.team[feature.key] ? (
                      <>
                        <Check className="h-5 w-5 text-green-500 mr-2 flex-shrink-0" />
                        <span className="text-gray-700">
                          {typeof planFeatures.team[feature.key] === 'string'
                            ? planFeatures.team[feature.key]
                            : feature.label}
                        </span>
                      </>
                    ) : (
                      <>
                        <X className="h-5 w-5 text-gray-300 mr-2 flex-shrink-0" />
                        <span className="text-gray-400">{feature.label}</span>
                      </>
                    )}
                  </li>
                ))}
              </ul>
            </CardContent>
            <CardFooter>
              <Button
                className="w-full"
                variant="outline"
                onClick={() => handleSelectPlan('team')}
              >
                Get Started
              </Button>
            </CardFooter>
          </Card>
        </div>

        {/* FAQ Section */}
        <div className="mt-16 text-center">
          <h2 className="text-3xl font-bold text-gray-900">Frequently Asked Questions</h2>
          <div className="mt-8 max-w-3xl mx-auto">
            <div className="space-y-6 text-left">
              <div>
                <h3 className="font-semibold text-lg">Can I change my plan later?</h3>
                <p className="mt-2 text-gray-600">
                  Yes, you can upgrade or downgrade your plan at any time. Upgrades take effect immediately,
                  while downgrades take effect at the end of your billing cycle.
                </p>
              </div>
              <div>
                <h3 className="font-semibold text-lg">What happens after my trial ends?</h3>
                <p className="mt-2 text-gray-600">
                  After your 14-day trial, you'll need to choose a paid plan to continue using the service.
                  Your data will be preserved, and you can upgrade at any time.
                </p>
              </div>
              <div>
                <h3 className="font-semibold text-lg">Do I need to enter payment details for the trial?</h3>
                <p className="mt-2 text-gray-600">
                  No, you can start your 14-day trial without entering any payment information.
                </p>
              </div>
              <div>
                <h3 className="font-semibold text-lg">What payment methods do you accept?</h3>
                <p className="mt-2 text-gray-600">
                  We accept all major credit/debit cards, UPI, net banking, and wallets through Razorpay.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}