import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { register as registerUserApi } from '../../api/auth';
import { SignupForm } from '../../components/ui/signup-form';
import useCustomSnackbar from '../../hooks/useNotifier';

const Register = () => {
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const { showSuccessToast, showErrorToast } = useCustomSnackbar();

  const {
    register,
    handleSubmit,
    watch,
    setValue,
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

  const handleRegistrationSubmit = async (data) => {
    try {
      setIsLoading(true);

      if (data.password1 && (!data.password2 || data.password2 !== data.password1)) {
        data.password2 = data.password1;
      }

      const payload = {
        email: data.email,
        password1: data.password1,
        password2: data.password2,
        first_name: data.first_name,
        last_name: data.last_name,
        organization_name: data.organization_name || null,
        organization_invite_id: data.organization_invite_id || null,
      };

      await registerUserApi(payload);
      showSuccessToast('Registration successful! Please check your email for verification.');
      
      setTimeout(() => {
        navigate('/login');
      }, 3000);
    } catch (err) {
      console.error('Registration error:', err);
      let errorMessage = 'Failed to register. Please try again.';
      if (typeof err === 'object' && err !== null && Object.keys(err).length > 0) {
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
        <SignupForm 
          onSubmit={handleSubmit(handleRegistrationSubmit)}
          register={register}
          errors={errors}
          isLoading={isLoading}
          watch={watch}
          setValue={setValue}
        />
        <div className="mt-6 text-center">
            <span className="text-neutral-600 dark:text-neutral-400">Already have an account? </span>
            <Link to="/login" className="font-medium text-primary hover:text-primary/90 dark:text-blue-400 dark:hover:text-blue-300 ml-1">
              Sign In
            </Link>
        </div>
      </div>
    </div>
  );
};

export default Register; 