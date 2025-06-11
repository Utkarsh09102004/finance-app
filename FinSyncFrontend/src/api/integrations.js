import axiosClient from './axios';

// Get all integrations for the current organization
export const getOrganizationIntegrations = async () => {
  try {
    const response = await axiosClient.get('/integrations/');
    return response.data;
  } catch (error) {
    throw error.response?.data || { detail: 'Failed to fetch integrations' };
  }
};

// Get a specific integration by ID
export const getIntegration = async (integrationId) => {
  try {
    const response = await axiosClient.get(`/integrations/${integrationId}/`);
    return response.data;
  } catch (error) {
    throw error.response?.data || { detail: 'Failed to fetch integration details' };
  }
};

// Disconnect/remove an integration
export const disconnectIntegration = async (integrationId) => {
  try {
    const response = await axiosClient.delete(`/integrations/${integrationId}/`);
    return response.data;
  } catch (error) {
    throw error.response?.data || { detail: 'Failed to disconnect integration' };
  }
};

// Initiate Zoho Books OAuth flow
export const initiateZohoBooksOAuth = async () => {
  try {
    const response = await axiosClient.get('/integrations/zohobooks/initiate/');
    
    // Store OAuth state and user/org info in localStorage for validation after redirect
    if (response.data.state) {
      localStorage.setItem('zohobooks_oauth_state', response.data.state);
      localStorage.setItem('zohobooks_user_id', response.data.user_id);
      localStorage.setItem('zohobooks_org_id', response.data.org_id);
    }
    
    return response.data;
  } catch (error) {
    throw error.response?.data || { detail: 'Failed to initiate Zoho Books integration' };
  }
};

// Fetch available external organizations for an integration
export const fetchExternalOrganizations = async (integrationId, provider) => {
  try {
    const response = await axiosClient.get(`/integrations/${provider}/${integrationId}/fetch-external-organizations/`);
    console.log('external organizations', response.data);
    return response.data;
  } catch (error) {
    throw error.response?.data || { detail: 'Failed to fetch external organizations' };
  }
};

// Set the selected external organization for an integration
export const setExternalOrganization = async (integrationId, provider, externalOrgId) => {
  try {
    const response = await axiosClient.post(`/integrations/${provider}/${integrationId}/set-external-organization/`, {
      external_organization_id: externalOrgId
    });
    return response.data;
  } catch (error) {
    throw error.response?.data || { detail: 'Failed to set external organization' };
  }
};

// Update integration details (like name)
export const updateIntegration = async (integrationId, data) => {
  try {
    const response = await axiosClient.patch(`/integrations/${integrationId}/`, data);
    return response.data;
  } catch (error) {
    throw error.response?.data || { detail: 'Failed to update integration' };
  }
}; 