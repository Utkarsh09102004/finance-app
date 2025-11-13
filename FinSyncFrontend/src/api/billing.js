import axiosClient from './axios';

// Billing API service for all payment-related operations
export const billingAPI = {
  // Fetch available pricing plans
  async getPricingPlans() {
    const response = await axiosClient.get('/billing/pricing/');
    return response.data;
  },

  // Get comprehensive billing overview
  async getBillingOverview() {
    const response = await axiosClient.get('/billing/overview/');
    return response.data;
  },

  // Create checkout session for new subscription or plan change
  async createCheckout(planName) {
    const response = await axiosClient.post('/billing/checkout/', {
      plan_name: planName,
    });
    return response.data;
  },

  // Update subscription plan (upgrade/downgrade)
  async updateSubscription(planName) {
    const response = await axiosClient.post('/billing/subscription/change/', {
      new_plan: planName,
    });
    return response.data;
  },

  // Cancel subscription
  async cancelSubscription(cancelImmediately = false) {
    const response = await axiosClient.post('/billing/subscription/cancel/', {
      cancel_immediately: cancelImmediately,
    });
    return response.data;
  },

  // Get all invoices
  async getInvoices(page = 1) {
    const response = await axiosClient.get('/billing/invoices/', {
      params: { page },
    });
    return response.data;
  },

  // Download specific invoice
  async downloadInvoice(invoiceId) {
    const response = await axiosClient.get(`/billing/invoices/${invoiceId}/download/`, {
      responseType: 'blob',
    });
    return response.data;
  },

  // Update billing contact information
  async updateBillingInfo(data) {
    const response = await axiosClient.post('/billing/billing-info/update/', data);
    return response.data;
  },

  // Get payment methods (if needed in future)
  async getPaymentMethods() {
    const response = await axiosClient.get('/billing/payment-methods/');
    return response.data;
  },

  // Verify payment after Razorpay redirect
  async verifyPayment(paymentData) {
    const response = await axiosClient.post('/billing/verify-payment/', paymentData);
    return response.data;
  },
};