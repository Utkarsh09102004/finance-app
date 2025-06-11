import axiosClient from './axios';

// Get current user's organization details
export const getMyOrganization = async () => {
  try {
    const response = await axiosClient.get('/organizations/my-organization/');
    return response.data;
  } catch (error) {
    throw error.response?.data || { detail: 'An error occurred fetching organization details' };
  }
};

// Get members of the organization
export const getOrganizationMembers = async (organization = null) => {
  try {
    const myOrg = organization || await getMyOrganization();
    
    // Then get all users who belong to this organization
    const response = await axiosClient.get(`/auth/users/?organization=${myOrg.id}`);
    return response.data;
  } catch (error) {
    throw error.response?.data || { detail: 'An error occurred fetching organization members' };
  }
};

// Invite a new member to the organization
export const inviteMember = async (email, organization = null) => {
  try {
    const myOrg = organization || await getMyOrganization();
    const response = await axiosClient.post(`/organizations/${myOrg.id}/invites/`, {
      email
    });
    return response.data;
  } catch (error) {
    throw error.response?.data || { detail: 'An error occurred inviting a member' };
  }
};

// Remove a member from the organization
export const removeMember = async (userId, organization = null) => {
  try {
    const myOrg = organization || await getMyOrganization();
    const response = await axiosClient.post(`/organizations/${myOrg.id}/members/${userId}/remove/`);
    return response.data;
  } catch (error) {
    throw error.response?.data || { detail: 'An error occurred removing the member' };
  }
};

// Leave the organization
export const leaveOrganization = async () => {
  try {
    const response = await axiosClient.post('/organizations/leave/');
    return response.data;
  } catch (error) {
    throw error.response?.data || { detail: 'An error occurred leaving the organization' };
  }
};

// Create a new organization
export const createOrganization = async (organizationData) => {
  try {
    const response = await axiosClient.post('/organizations/create/', organizationData);
    return response.data;
  } catch (error) {
    throw error.response?.data || { detail: 'An error occurred creating the organization' };
  }
};

// Get list of organization invites
export const getOrganizationInvites = async (organization = null) => {
  try {
    const myOrg = organization || await getMyOrganization();
    const response = await axiosClient.get(`/organizations/${myOrg.id}/invites/`);
    return response.data;
  } catch (error) {
    throw error.response?.data || { detail: 'An error occurred fetching invites' };
  }
}; 