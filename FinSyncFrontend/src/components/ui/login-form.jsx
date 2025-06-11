"use client";
import React, { useState } from "react";
import { Link } from 'react-router-dom'; // For Forgot Password link
import { Label } from "./label";
import { Input } from "./input";
import { cn } from "../../lib/utils";
import { IconEye, IconEyeOff } from "@tabler/icons-react"; // Icons for password toggle
// Icons can be added later if social login is implemented for the login page too
// import {
//   IconBrandGithub,
//   IconBrandGoogle,
// } from "@tabler/icons-react";

// Props:
// - onSubmit (function from react-hook-form handleSubmit)
// - register (function from react-hook-form)
// - errors (object from react-hook-form formState)
// - isLoading (boolean for submission state)
// apiError prop is no longer used, removed.

export function LoginForm({ onSubmit, register, errors, isLoading }) {
  const [showPassword, setShowPassword] = useState(false);

  const togglePasswordVisibility = () => {
    setShowPassword(!showPassword);
  };

  return (
    <div className="w-full mx-auto rounded-none md:rounded-2xl p-4 md:p-8 shadow-input bg-white dark:bg-black">
      <h2 className="font-bold text-xl text-neutral-800 dark:text-neutral-200">
        Welcome Back to FinSync
      </h2>
      <p className="text-neutral-600 text-sm max-w-sm mt-2 dark:text-neutral-300">
        Login to access your FinSync dashboard.
      </p>

      <form className="my-8" onSubmit={onSubmit}>
        <LabelInputContainer className="mb-4">
          <Label htmlFor="email">Email Address</Label>
          <Input 
            id="email" 
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

        <LabelInputContainer className="mb-4">
          <Label htmlFor="password">Password</Label>
          <div className="relative">
            <Input 
              id="password" 
              placeholder="••••••••" 
              type={showPassword ? "text" : "password"} 
              {...register('password', { required: 'Password is required' })}
              aria-invalid={errors.password ? "true" : "false"}
              className="pr-10" // Add padding to make space for the icon
            />
            <button 
              type="button"
              onClick={togglePasswordVisibility}
              className="absolute inset-y-0 right-0 pr-3 flex items-center text-sm leading-5 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
              aria-label={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? (
                <IconEyeOff className="h-5 w-5" />
              ) : (
                <IconEye className="h-5 w-5" />
              )}
            </button>
          </div>
          {errors.password && <p className="text-red-500 text-xs mt-1">{errors.password.message}</p>}
        </LabelInputContainer>
        
        <div className="flex items-center justify-end mb-8">
          <div className="text-sm">
              <Link to="/forgot-password" className="font-medium text-primary hover:text-primary/90 dark:text-blue-400 dark:hover:text-blue-300">
                  Forgot your password?
              </Link>
          </div>
        </div>

        <button
          className="bg-gradient-to-br relative group/btn from-black dark:from-zinc-900 dark:to-zinc-900 to-neutral-600 block dark:bg-zinc-800 w-full text-white rounded-md h-10 font-medium shadow-[0px_1px_0px_0px_#ffffff40_inset,0px_-1px_0px_0px_#ffffff40_inset] dark:shadow-[0px_1px_0px_0px_var(--zinc-800)_inset,0px_-1px_0px_0px_var(--zinc-800)_inset] disabled:opacity-70"
          type="submit"
          disabled={isLoading}
        >
          {isLoading ? (
            <>
              <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2 inline-block"></span>
              Signing In...
            </>
          ) : (
            <>
              Sign In &rarr;
              <BottomGradient />
            </>
          )}
        </button>

        {/* Social logins can be added here if needed, similar to SignupForm */}
        {/* <div className="bg-gradient-to-r from-transparent via-neutral-300 dark:via-neutral-700 to-transparent my-8 h-[1px] w-full" /> */}
        {/* <div className="flex flex-col space-y-4"> ...social buttons... </div> */}
      </form>
    </div>
  );
}

const BottomGradient = () => {
  return (
    <>
      <span className="group-hover/btn:opacity-100 block transition duration-500 opacity-0 absolute h-px w-full -bottom-px inset-x-0 bg-gradient-to-r from-transparent via-cyan-500 to-transparent" />
      <span className="group-hover/btn:opacity-100 blur-sm block transition duration-500 opacity-0 absolute h-px w-1/2 mx-auto -bottom-px inset-x-10 bg-gradient-to-r from-transparent via-indigo-500 to-transparent" />
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