import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Progress } from '../ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { 
  AlertDialog, 
  AlertDialogAction, 
  AlertDialogCancel, 
  AlertDialogContent, 
  AlertDialogDescription, 
  AlertDialogFooter, 
  AlertDialogHeader, 
  AlertDialogTitle 
} from '../ui/alert-dialog';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import useCustomSnackbar from '../../hooks/useNotifier';
import { billingAPI } from '../../api/billing';
import { useAuth } from '../../contexts/AuthContext';
import { 
  CreditCard, 
  Download, 
  AlertCircle, 
  CheckCircle, 
  Clock,
  Users,
  Zap,
  Calendar,
  Receipt,
  Loader2,
  AlertTriangle,
  Mail,
  Phone,
  User
} from 'lucide-react';
import { format, formatDistanceToNow } from 'date-fns';
import { useNavigate } from 'react-router-dom';

export default function BillingSettings() {
  const [billingData, setBillingData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false);
  const [cancellingSubscription, setCancellingSubscription] = useState(false);
  const [updatingBillingInfo, setUpdatingBillingInfo] = useState(false);
  const [billingInfo, setBillingInfo] = useState({
    billing_email: '',
    billing_name: '',
    billing_phone: '',
  });
  const { showSuccessToast, showErrorToast } = useCustomSnackbar();
  const { user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    fetchBillingData();
  }, []);

  const fetchBillingData = async () => {
    try {
      const data = await billingAPI.getBillingOverview();
      setBillingData(data);
      setBillingInfo({
        billing_email: data.organization.billing_email || '',
        billing_name: data.organization.billing_name || '',
        billing_phone: data.organization.billing_phone || '',
      });
    } catch (error) {
      console.error('Failed to fetch billing data:', error);
      showErrorToast('Failed to load billing information');
    } finally {
      setLoading(false);
    }
  };

  const handleCancelSubscription = async () => {
    setCancellingSubscription(true);
    try {
      await billingAPI.cancelSubscription(false);
      showSuccessToast('Your subscription will be cancelled at the end of the billing period.');
      setCancelDialogOpen(false);
      fetchBillingData();
    } catch (error) {
      showErrorToast('Failed to cancel subscription');
    } finally {
      setCancellingSubscription(false);
    }
  };

  const handleUpdateBillingInfo = async () => {
    setUpdatingBillingInfo(true);
    try {
      await billingAPI.updateBillingInfo(billingInfo);
      showSuccessToast('Billing information updated successfully');
      fetchBillingData();
    } catch (error) {
      showErrorToast('Failed to update billing information');
    } finally {
      setUpdatingBillingInfo(false);
    }
  };

  const getStatusBadge = (status) => {
    const statusConfig = {
      trialing: { label: 'Trial', variant: 'secondary', icon: Clock },
      active: { label: 'Active', variant: 'default', icon: CheckCircle },
      past_due: { label: 'Past Due', variant: 'destructive', icon: AlertCircle },
      canceled: { label: 'Cancelled', variant: 'secondary', icon: AlertCircle },
      inactive: { label: 'Inactive', variant: 'secondary', icon: AlertCircle },
    };

    const config = statusConfig[status] || statusConfig.inactive;
    const Icon = config.icon;

    return (
      <Badge variant={config.variant} className="flex items-center gap-1">
        <Icon className="h-3 w-3" />
        {config.label}
      </Badge>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    );
  }

  if (!billingData) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">Unable to load billing information</p>
      </div>
    );
  }

  const { organization, usage, approaching_limits, recent_payments, recent_invoices, subscription_history } = billingData;

  return (
    <div className="space-y-6">
      {/* Subscription Overview */}
      <Card>
        <CardHeader>
          <div className="flex justify-between items-start">
            <div>
              <CardTitle>Subscription Overview</CardTitle>
              <CardDescription>
                Manage your subscription and billing information
              </CardDescription>
            </div>
            {organization.subscription_status === 'active' && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCancelDialogOpen(true)}
              >
                Cancel Subscription
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-2 gap-6">
            <div>
              <h3 className="font-semibold mb-4">Current Plan</h3>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Plan</span>
                  <span className="font-medium">{organization.subscription_plan?.display_name || 'No Plan'}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Status</span>
                  {getStatusBadge(organization.subscription_status)}
                </div>
                {organization.trial_ends_at && (
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">Trial Ends</span>
                    <span className="font-medium">
                      {formatDistanceToNow(new Date(organization.trial_ends_at), { addSuffix: true })}
                    </span>
                  </div>
                )}
                {organization.subscription_end_date && (
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">Subscription Ends</span>
                    <span className="font-medium">
                      {format(new Date(organization.subscription_end_date), 'MMM dd, yyyy')}
                    </span>
                  </div>
                )}
                {organization.payment_failed_count > 0 && (
                  <div className="bg-red-50 p-3 rounded-lg flex items-start gap-2">
                    <AlertTriangle className="h-4 w-4 text-red-600 mt-0.5" />
                    <div className="text-sm">
                      <p className="font-medium text-red-900">Payment Issues</p>
                      <p className="text-red-700">
                        {organization.payment_failed_count} failed payment{organization.payment_failed_count > 1 ? 's' : ''}.
                        {organization.grace_period_ends_at && (
                          <span> Grace period ends {formatDistanceToNow(new Date(organization.grace_period_ends_at), { addSuffix: true })}.</span>
                        )}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div>
              <h3 className="font-semibold mb-4">Usage</h3>
              <div className="space-y-4">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <Users className="h-4 w-4 text-gray-600" />
                      <span className="text-sm text-gray-600">Users</span>
                    </div>
                    <span className="text-sm font-medium">
                      {usage.users.current} / {usage.users.limit}
                    </span>
                  </div>
                  <Progress value={usage.users.percentage} className="h-2" />
                </div>
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <Zap className="h-4 w-4 text-gray-600" />
                      <span className="text-sm text-gray-600">Integrations</span>
                    </div>
                    <span className="text-sm font-medium">
                      {usage.integrations.current} / {usage.integrations.limit}
                    </span>
                  </div>
                  <Progress value={usage.integrations.percentage} className="h-2" />
                </div>
              </div>

              {approaching_limits.length > 0 && (
                <div className="mt-4 bg-amber-50 p-3 rounded-lg">
                  <p className="text-sm font-medium text-amber-900 mb-1">Approaching Limits</p>
                  {approaching_limits.map((limit, index) => (
                    <p key={index} className="text-sm text-amber-700">{limit.message}</p>
                  ))}
                </div>
              )}
            </div>
          </div>

          {billingData.can_upgrade && (
            <div className="mt-6 pt-6 border-t">
              <Button 
                onClick={() => navigate('/pricing')}
                className="w-full sm:w-auto"
              >
                Upgrade Plan
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Tabs for detailed information */}
      <Tabs defaultValue="invoices" className="w-full">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="invoices">Invoices</TabsTrigger>
          <TabsTrigger value="payments">Payments</TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
          <TabsTrigger value="settings">Settings</TabsTrigger>
        </TabsList>

        <TabsContent value="invoices" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Invoices</CardTitle>
              <CardDescription>Download your past invoices</CardDescription>
            </CardHeader>
            <CardContent>
              {recent_invoices.length === 0 ? (
                <p className="text-sm text-gray-500">No invoices yet</p>
              ) : (
                <div className="space-y-3">
                  {recent_invoices.map((invoice) => (
                    <div key={invoice.id} className="flex items-center justify-between py-3 border-b last:border-0">
                      <div className="flex items-center gap-3">
                        <Receipt className="h-4 w-4 text-gray-400" />
                        <div>
                          <p className="font-medium">{invoice.invoice_number}</p>
                          <p className="text-sm text-gray-600">
                            {format(new Date(invoice.created_at), 'MMM dd, yyyy')}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="font-medium">
                          {invoice.currency} {invoice.total_amount}
                        </span>
                        {invoice.invoice_url && (
                          <Button 
                            variant="ghost" 
                            size="sm"
                            onClick={() => window.open(invoice.invoice_url, '_blank')}
                          >
                            <Download className="h-4 w-4" />
                          </Button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="payments" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Recent Payments</CardTitle>
              <CardDescription>Your payment history</CardDescription>
            </CardHeader>
            <CardContent>
              {recent_payments.length === 0 ? (
                <p className="text-sm text-gray-500">No payments yet</p>
              ) : (
                <div className="space-y-3">
                  {recent_payments.map((payment) => (
                    <div key={payment.id} className="flex items-center justify-between py-3 border-b last:border-0">
                      <div className="flex items-center gap-3">
                        <CreditCard className="h-4 w-4 text-gray-400" />
                        <div>
                          <p className="font-medium">
                            {payment.currency} {payment.amount}
                          </p>
                          <p className="text-sm text-gray-600">
                            {payment.payment_method} • {format(new Date(payment.created_at), 'MMM dd, yyyy')}
                          </p>
                        </div>
                      </div>
                      <Badge 
                        variant={payment.status === 'COMPLETED' ? 'default' : 'destructive'}
                      >
                        {payment.status}
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="history" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Subscription History</CardTitle>
              <CardDescription>Changes to your subscription</CardDescription>
            </CardHeader>
            <CardContent>
              {subscription_history.length === 0 ? (
                <p className="text-sm text-gray-500">No subscription changes yet</p>
              ) : (
                <div className="space-y-3">
                  {subscription_history.map((event) => (
                    <div key={event.id} className="flex items-center justify-between py-3 border-b last:border-0">
                      <div className="flex items-center gap-3">
                        <Calendar className="h-4 w-4 text-gray-400" />
                        <div>
                          <p className="font-medium">{event.action}</p>
                          <p className="text-sm text-gray-600">
                            {event.from_plan && `From ${event.from_plan.display_name}`}
                            {event.from_plan && event.to_plan && ' → '}
                            {event.to_plan && `To ${event.to_plan.display_name}`}
                          </p>
                        </div>
                      </div>
                      <span className="text-sm text-gray-600">
                        {format(new Date(event.created_at), 'MMM dd, yyyy')}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="settings" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Billing Information</CardTitle>
              <CardDescription>Update your billing contact details</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div>
                  <Label htmlFor="billing_email">Billing Email</Label>
                  <div className="flex gap-2 mt-1">
                    <Mail className="h-4 w-4 text-gray-400 mt-2.5" />
                    <Input
                      id="billing_email"
                      type="email"
                      value={billingInfo.billing_email}
                      onChange={(e) => setBillingInfo({ ...billingInfo, billing_email: e.target.value })}
                      placeholder="billing@company.com"
                    />
                  </div>
                </div>
                <div>
                  <Label htmlFor="billing_name">Billing Name</Label>
                  <div className="flex gap-2 mt-1">
                    <User className="h-4 w-4 text-gray-400 mt-2.5" />
                    <Input
                      id="billing_name"
                      value={billingInfo.billing_name}
                      onChange={(e) => setBillingInfo({ ...billingInfo, billing_name: e.target.value })}
                      placeholder="Company Name"
                    />
                  </div>
                </div>
                <div>
                  <Label htmlFor="billing_phone">Billing Phone</Label>
                  <div className="flex gap-2 mt-1">
                    <Phone className="h-4 w-4 text-gray-400 mt-2.5" />
                    <Input
                      id="billing_phone"
                      value={billingInfo.billing_phone}
                      onChange={(e) => setBillingInfo({ ...billingInfo, billing_phone: e.target.value })}
                      placeholder="+91 98765 43210"
                    />
                  </div>
                </div>
                <Button 
                  onClick={handleUpdateBillingInfo}
                  disabled={updatingBillingInfo}
                >
                  {updatingBillingInfo ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Updating...
                    </>
                  ) : (
                    'Update Billing Information'
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Cancel Subscription Dialog */}
      <AlertDialog open={cancelDialogOpen} onOpenChange={setCancelDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cancel Subscription?</AlertDialogTitle>
            <AlertDialogDescription>
              Your subscription will be cancelled at the end of the current billing period. 
              You'll continue to have access until then.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep Subscription</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleCancelSubscription}
              disabled={cancellingSubscription}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {cancellingSubscription ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Cancelling...
                </>
              ) : (
                'Cancel Subscription'
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}