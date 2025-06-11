"use client";
import React, { useState, useEffect } from "react";
import { Label } from "./label"; // Local path
import { Input } from "./input";   // Local path
import { cn } from "../../lib/utils"; // Adjusted path
import {
  IconBrandGithub,
  IconBrandGoogle,
  IconChevronRight,
  IconArrowLeft,
} from "@tabler/icons-react";

// Props: 
// - onSubmit (function from react-hook-form handleSubmit)
// - register (function from react-hook-form)
// - errors (object from react-hook-form formState)
// - isLoading (boolean for submission state)
// - apiError (string for API errors)
// - successMessage (string for success message)
// - watch (function from react-hook-form to watch fields)
// - setValue (function from react-hook-form to set values)

export function SignupForm({ onSubmit, register, errors, isLoading, apiError, successMessage, watch, setValue }) {
  const [step, setStep] = useState(1);
  const [orgChoice, setOrgChoice] = useState(null); // 'create' or 'join'
  
  // Form steps:
  // 1. Personal Information
  // 2. Organization Choice
  // 3. Organization Details
  
  // Update password2 whenever password1 changes
  useEffect(() => {
    if (watch && setValue) {
      const subscription = watch((value, { name }) => {
        if (name === 'password1') {
          setValue('password2', value.password1);
        }
      });
      return () => subscription.unsubscribe();
    }
  }, [watch, setValue]);
  
  const goToNextStep = (e) => {
    e.preventDefault();
    
    // Validation for Step 1
    if (step === 1) {
      if (!watch('first_name') || !watch('last_name') || !watch('email') || !watch('password1')) {
        return; // Don't proceed if required fields are missing
      }
      
      if (errors.first_name || errors.last_name || errors.email || errors.password1) {
        return; // Don't proceed if there are errors
      }
    }
    
    setStep(step + 1);
  };
  
  const goToPrevStep = (e) => {
    e.preventDefault();
    if (step > 1) {
      setStep(step - 1);
    }
  };
  
  const handleOrgChoice = (choice) => {
    setOrgChoice(choice);
    setStep(3);
  };

  return (
    <div className="w-full mx-auto rounded-none md:rounded-2xl p-4 md:p-8 shadow-input bg-white dark:bg-black">
      <h2 className="font-bold text-xl text-neutral-800 dark:text-neutral-200">
        Create Your FinSync Account
      </h2>
      <p className="text-neutral-600 text-sm max-w-sm mt-2 dark:text-neutral-300">
        Join FinSync to get clarity on your startup's finances.
      </p>

      {/* Progress indicator */}
      <div className="my-6">
        <div className="flex items-center justify-between">
          <div className={`flex items-center justify-center w-8 h-8 rounded-full ${step >= 1 ? 'bg-black text-white dark:bg-white dark:text-black' : 'bg-gray-200 text-gray-500 dark:bg-zinc-800'}`}>1</div>
          <div className={`flex-1 h-1 mx-2 ${step >= 2 ? 'bg-black dark:bg-white' : 'bg-gray-200 dark:bg-zinc-800'}`}></div>
          <div className={`flex items-center justify-center w-8 h-8 rounded-full ${step >= 2 ? 'bg-black text-white dark:bg-white dark:text-black' : 'bg-gray-200 text-gray-500 dark:bg-zinc-800'}`}>2</div>
          <div className={`flex-1 h-1 mx-2 ${step >= 3 ? 'bg-black dark:bg-white' : 'bg-gray-200 dark:bg-zinc-800'}`}></div>
          <div className={`flex items-center justify-center w-8 h-8 rounded-full ${step >= 3 ? 'bg-black text-white dark:bg-white dark:text-black' : 'bg-gray-200 text-gray-500 dark:bg-zinc-800'}`}>3</div>
        </div>
        <div className="flex justify-between mt-1 text-xs text-gray-500 dark:text-gray-400">
          <span className="w-8 text-center">Profile</span>
          <span className="w-16 text-center">Organization</span>
          <span className="w-8 text-center">Details</span>
        </div>
      </div>

      {/* The form should always be visible unless an external success condition is met (handled by parent) */}
      <form className="my-4" onSubmit={onSubmit}>
        {/* Step 1: Personal Information */}
        {step === 1 && (
          <div className="space-y-4">
            <div className="flex flex-col md:flex-row space-y-4 md:space-y-0 md:space-x-4">
              <LabelInputContainer>
                <Label htmlFor="first_name">First name</Label>
                <Input 
                  id="first_name" 
                  placeholder="Tyler" 
                  type="text" 
                  {...register('first_name', { required: 'First name is required' })}
                  aria-invalid={errors.first_name ? "true" : "false"}
                />
                {errors.first_name && <p className="text-red-500 text-xs mt-1">{errors.first_name.message}</p>}
              </LabelInputContainer>
              <LabelInputContainer>
                <Label htmlFor="last_name">Last name</Label>
                <Input 
                  id="last_name" 
                  placeholder="Durden" 
                  type="text" 
                  {...register('last_name', { required: 'Last name is required' })}
                  aria-invalid={errors.last_name ? "true" : "false"}
                />
                {errors.last_name && <p className="text-red-500 text-xs mt-1">{errors.last_name.message}</p>}
              </LabelInputContainer>
            </div>

            <LabelInputContainer>
              <Label htmlFor="emailReg">Email Address</Label>
              <Input 
                id="emailReg" 
                placeholder="you@example.com" 
                type="email" 
                {...register('email', {
                  required: 'Email is required',
                  pattern: {
                    value: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
                    message: 'Invalid email address',
                  },
                })}
                aria-invalid={errors.email ? "true" : "false"}
              />
              {errors.email && <p className="text-red-500 text-xs mt-1">{errors.email.message}</p>}
            </LabelInputContainer>

            <LabelInputContainer>
              <Label htmlFor="password1Reg">Password</Label>
              <Input 
                id="password1Reg" 
                placeholder="••••••••" 
                type="password" 
                {...register('password1', {
                  required: 'Password is required',
                  minLength: {
                    value: 8,
                    message: 'Password must be at least 8 characters',
                  },
                })}
                aria-invalid={errors.password1 ? "true" : "false"}
                onChange={(e) => {
                  if (setValue) {
                    setValue('password2', e.target.value);
                  }
                }}
              />
              {errors.password1 && <p className="text-red-500 text-xs mt-1">{errors.password1.message}</p>}
              
              {/* Register password2 but keep it hidden */}
              <input type="hidden" {...register('password2', { required: true })} />
            </LabelInputContainer>

            <button
              onClick={goToNextStep}
              className="bg-black dark:bg-white relative group/btn block dark:text-black text-white w-full rounded-md h-10 font-medium shadow-[0px_1px_0px_0px_#ffffff40_inset,0px_-1px_0px_0px_#ffffff40_inset] dark:shadow-[0px_1px_0px_0px_var(--zinc-800)_inset,0px_-1px_0px_0px_var(--zinc-800)_inset]"
              type="button"
            >
              Continue <IconChevronRight className="inline-block ml-1 h-4 w-4" />
              <BottomGradient />
            </button>
          </div>
        )}

        {/* Step 2: Organization Choice */}
        {step === 2 && (
          <div className="space-y-6">
            <h3 className="font-medium text-lg text-center mb-4">Would you like to:</h3>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <button
                type="button"
                onClick={() => handleOrgChoice('create')}
                className="relative group/btn p-6 rounded-lg border-2 border-transparent hover:border-black dark:hover:border-white bg-gray-50 dark:bg-zinc-900 flex flex-col items-center justify-center h-40 transition-all duration-200"
              >
                <div className="w-12 h-12 mb-3 rounded-full bg-gray-200 dark:bg-zinc-800 flex items-center justify-center">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-black dark:text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                  </svg>
                </div>
                <span className="font-medium text-gray-800 dark:text-white">Create a new organization</span>
                <p className="text-xs text-gray-500 dark:text-gray-400 text-center mt-2">Start fresh with your own financial space</p>
                <BottomGradient />
              </button>
              
              <button
                type="button"
                onClick={() => handleOrgChoice('join')}
                className="relative group/btn p-6 rounded-lg border-2 border-transparent hover:border-black dark:hover:border-white bg-gray-50 dark:bg-zinc-900 flex flex-col items-center justify-center h-40 transition-all duration-200"
              >
                <div className="w-12 h-12 mb-3 rounded-full bg-gray-200 dark:bg-zinc-800 flex items-center justify-center">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-black dark:text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                  </svg>
                </div>
                <span className="font-medium text-gray-800 dark:text-white">Join an existing organization</span>
                <p className="text-xs text-gray-500 dark:text-gray-400 text-center mt-2">Use an invite code to join a team</p>
                <BottomGradient />
              </button>
            </div>
            
            <button
              onClick={goToPrevStep}
              className="w-full mt-4 flex items-center justify-center text-gray-600 dark:text-gray-400 hover:text-black hover:dark:text-white transition-colors"
              type="button"
            >
              <IconArrowLeft className="h-4 w-4 mr-1" /> Back to personal details
            </button>
          </div>
        )}

        {/* Step 3: Organization Details */}
        {step === 3 && (
          <div className="space-y-4">
            <h3 className="font-medium text-lg mb-4">
              {orgChoice === 'create' ? 'Create a new organization' : 'Join an existing organization'}
            </h3>
            
            {orgChoice === 'create' ? (
              <LabelInputContainer>
                <Label htmlFor="organization_name">Organization Name</Label>
                <Input 
                  id="organization_name" 
                  placeholder="Acme Inc." 
                  type="text" 
                  {...register('organization_name', { 
                    required: orgChoice === 'create' ? 'Organization name is required' : false 
                  })}
                  aria-invalid={errors.organization_name ? "true" : "false"}
                />
                {errors.organization_name && <p className="text-red-500 text-xs mt-1">{errors.organization_name.message}</p>}
              </LabelInputContainer>
            ) : (
              <LabelInputContainer>
                <Label htmlFor="organization_invite_id">Organization Invite Code</Label>
                <Input 
                  id="organization_invite_id" 
                  placeholder="INVITE_CODE_XYZ" 
                  type="text" 
                  {...register('organization_invite_id', { 
                    required: orgChoice === 'join' ? 'Invite code is required' : false 
                  })}
                  aria-invalid={errors.organization_invite_id ? "true" : "false"}
                />
                {errors.organization_invite_id && <p className="text-red-500 text-xs mt-1">{errors.organization_invite_id.message}</p>}
                <p className="text-neutral-600 text-xs max-w-sm mt-1 dark:text-neutral-400">
                  Please enter the invitation code you received to join this organization.
                </p>
              </LabelInputContainer>
            )}
            
            <div className="flex flex-col space-y-3 pt-4">
              <button
                className="bg-black dark:bg-white relative group/btn block dark:text-black text-white w-full rounded-md h-10 font-medium shadow-[0px_1px_0px_0px_#ffffff40_inset,0px_-1px_0px_0px_#ffffff40_inset] dark:shadow-[0px_1px_0px_0px_var(--zinc-800)_inset,0px_-1px_0px_0px_var(--zinc-800)_inset] disabled:opacity-70"
                type="submit"
                disabled={isLoading}
              >
                {isLoading ? (
                  <>
                    <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-white dark:border-black mr-2 inline-block"></span>
                    Processing...
                  </>
                ) : (
                  <>
                    Complete Registration &rarr;
                    <BottomGradient />
                  </>
                )}
              </button>
              
              <button
                onClick={goToPrevStep}
                className="text-gray-600 dark:text-gray-400 hover:text-black hover:dark:text-white transition-colors text-sm"
                type="button"
              >
                <IconArrowLeft className="h-4 w-4 inline-block mr-1" /> Back to previous step
              </button>
            </div>
          </div>
        )}
      </form>

      <div className="bg-gradient-to-r from-transparent via-neutral-300 dark:via-neutral-700 to-transparent my-8 h-[1px] w-full" />

      <div className="flex flex-col space-y-4">
        {/* Placeholder for social logins, can be activated later */}
        <button
          className="relative group/btn flex space-x-2 items-center justify-start px-4 w-full text-black rounded-md h-10 font-medium shadow-input bg-gray-50 dark:bg-zinc-900 dark:shadow-[0px_0px_1px_1px_var(--neutral-800)] disabled:opacity-70"
          type="button" // Changed to button to prevent form submission if wrapped in form
          disabled={true} // Disabled for now
        >
          <IconBrandGithub className="h-4 w-4 text-neutral-800 dark:text-neutral-300" />
          <span className="text-neutral-700 dark:text-neutral-300 text-sm">
            Sign up with GitHub
          </span>
          <BottomGradient />
        </button>
        <button
          className="relative group/btn flex space-x-2 items-center justify-start px-4 w-full text-black rounded-md h-10 font-medium shadow-input bg-gray-50 dark:bg-zinc-900 dark:shadow-[0px_0px_1px_1px_var(--neutral-800)] disabled:opacity-70"
          type="button" // Changed to button
          disabled={true} // Disabled for now
        >
          <IconBrandGoogle className="h-4 w-4 text-neutral-800 dark:text-neutral-300" />
          <span className="text-neutral-700 dark:text-neutral-300 text-sm">
            Sign up with Google
          </span>
          <BottomGradient />
        </button>
      </div>
    </div>
  );
}

const BottomGradient = () => {
  return (
    <>
      <span className="group-hover/btn:opacity-100 block transition duration-500 opacity-0 absolute h-px w-full -bottom-px inset-x-0 bg-gradient-to-r from-transparent via-gray-500 dark:via-gray-300 to-transparent" />
      <span className="group-hover/btn:opacity-100 blur-sm block transition duration-500 opacity-0 absolute h-px w-1/2 mx-auto -bottom-px inset-x-10 bg-gradient-to-r from-transparent via-gray-500 dark:via-gray-300 to-transparent" />
    </>
  );
};

const LabelInputContainer = ({ children, className }) => {
  return (
    <div className={cn("flex flex-col space-y-2 w-full", className)}>
      {children}
    </div>
  );
}; 