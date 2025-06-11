import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { login as loginUserApi } from '../../api/auth';
import { LoginForm } from '../../components/ui/login-form';
import { useAuth } from '../../contexts/AuthContext';
import useCustomSnackbar from '../../hooks/useNotifier';

const Login = () => {
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const { login: contextLogin } = useAuth();
  const { showSuccessToast, showErrorToast } = useCustomSnackbar();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm();

  useEffect(() => {
    const fieldErrors = Object.values(errors);
    if (fieldErrors.length > 0) {
      fieldErrors.forEach(error => {
        if (error && error.message) {
          showErrorToast(error.message);
        }
      });
    }
  }, [errors, showErrorToast]);

  const handleLoginSubmit = async (data) => {
    try {
      setIsLoading(true);

      const response = await loginUserApi(data.email, data.password);
      
      contextLogin(response.access, response.refresh, response.user);
      showSuccessToast('Login successful! Redirecting...');

      setTimeout(() => {
        navigate('/dashboard');
      }, 1500);
    } catch (err) {
      console.error('Login error:', err);
      let errorMessage = 'Failed to login. Please check your credentials and try again.';
      if (typeof err === 'object' && err !== null && err.detail) {
        errorMessage = err.detail;
      } else if (typeof err === 'object' && err !== null && Object.keys(err).length > 0) {
        const backendErrors = Object.entries(err)
          .map(([key, value]) => {
            const fieldName = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
            if (Array.isArray(value)) return `${fieldName}: ${value.join(', ')}`;
            return `${fieldName}: ${String(value)}`;
          });
        if (backendErrors.length > 0) {
          errorMessage = backendErrors.join('; ');
        }
      } else if (typeof err === 'string' && err) {
        errorMessage = err;
      }
      showErrorToast(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-page-container">
      <div className="flex flex-col items-center w-full max-w-md">
        <LoginForm
          onSubmit={handleSubmit(handleLoginSubmit)}
          register={register}
          errors={errors}
          isLoading={isLoading}
        />
        <div className="mt-6 text-center">
          <span className="text-neutral-600 dark:text-neutral-400">Don't have an account? </span>
          <Link to="/register" className="font-medium text-primary hover:text-primary/90 dark:text-blue-400 dark:hover:text-blue-300 ml-1">
            Sign Up
          </Link>
        </div>
      </div>
    </div>
  );
};

export default Login; 