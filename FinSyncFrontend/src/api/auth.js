import axiosClient from './axios';



export const login = async (email, password) => {
  try {
    console.log("hello")
    const response = await axiosClient.post('/auth/login/', {
      email,
      password,
    });
    console.log(response.data)
    // Store tokens in localStorage
    if (response.data.access) {
      localStorage.setItem('accessToken', response.data.access);

    }
    if (response.data.refresh) {
      localStorage.setItem('refreshToken', response.data.refresh);
    }

    return response.data;
  } catch (error) {
    throw error.response?.data || { detail: 'An error occurred during login' };
  }
};

export const register = async (userData) => {
  try {
    const response = await axiosClient.post('/auth/registration/', userData);
    return response.data;
  } catch (error) {
    throw error.response?.data || { detail: 'An error occurred during registration' };
  }
};

export const logout = () => {
  // Remove tokens from localStorage
  localStorage.removeItem('accessToken');
  localStorage.removeItem('refreshToken');
  
  // Optional: Call backend to invalidate token
  return axiosClient.post('/auth/logout/');
};

export const getCurrentUser = async () => {
  try {
    const response = await axiosClient.get('/auth/user/');
    return response.data;
  } catch (error) {
    return null;
  }
};

export const isAuthenticated = () => {
  return !!localStorage.getItem('accessToken');
}; 