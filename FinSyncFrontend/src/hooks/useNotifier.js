import { useSnackbar } from 'notistack';

const useCustomSnackbar = () => {
  const { enqueueSnackbar } = useSnackbar();

  const showSuccessToast = (message) => {
    enqueueSnackbar(message, { 
      variant: 'success',
      className: 'bg-green-500 text-white',
    });
  };

  const showErrorToast = (message) => {
    enqueueSnackbar(message, { 
      variant: 'error',
      className: 'bg-red-500 text-white',
    });
  };

  const showWarningToast = (message) => {
    enqueueSnackbar(message, { 
      variant: 'warning',
      className: 'bg-yellow-500 text-black',
    });
  };
  
  const showInfoToast = (message) => {
    enqueueSnackbar(message, { 
      variant: 'info',
      className: 'bg-blue-500 text-white',
    });
  };

  return { showSuccessToast, showErrorToast, showWarningToast, showInfoToast };
};

export default useCustomSnackbar; 