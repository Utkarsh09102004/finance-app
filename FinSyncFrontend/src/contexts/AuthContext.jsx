import { createContext, useContext, useState, useEffect } from 'react';
import { getCurrentUser, isAuthenticated } from '../api/auth';

// Create the auth context
const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isAuth, setIsAuth] = useState(false);

  const fetchUserAndAuthStatus = async () => {
    try {
      setLoading(true);
      const authenticated = isAuthenticated(); // Checks for token existence
      setIsAuth(authenticated);

      if (authenticated) {
        const userData = await getCurrentUser();
        setUser(userData);
      } else {
        setUser(null);
        // Clear tokens if not authenticated, just in case they are stale
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
      }
    } catch (error) {
      console.error('Auth state fetch failed:', error);
      setUser(null);
      setIsAuth(false);
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUserAndAuthStatus();
  }, []);

  const login = (accessToken, refreshToken, userData) => {
    localStorage.setItem('access_token', accessToken);
    localStorage.setItem('refresh_token', refreshToken);
    setUser(userData);
    setIsAuth(true);
    // Optionally, you can call fetchUserAndAuthStatus() again if you want to re-verify from backend
    // but typically setting user and isAuth directly is fine after successful login API call.
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setUser(null);
    setIsAuth(false);
    // Here you might want to redirect to login page, e.g., using navigate() if passed or handled in component
  };

  // This function can be used if you need to manually trigger a re-check of auth state
  // For example, after a token refresh or a significant profile update.
  const updateAuthState = async () => {
    await fetchUserAndAuthStatus();
  };

  // Provide auth context
  const value = {
    user,
    isAuth,
    loading,
    login,      // Add login function to context
    logout,     // Add logout function to context
    updateAuthState,
    setUser, // Still useful for direct manipulation if needed, e.g., profile update
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

// Custom hook to use auth context
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}; 