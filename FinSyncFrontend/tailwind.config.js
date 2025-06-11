/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'], 
  content: [
    './index.html', // Ensure base HTML is scanned
    './src/**/*.{js,jsx,ts,tsx}', // Covers all relevant files in src
  ],
  prefix: '', 
  theme: {
    container: {
      center: true,
      padding: '2rem',
      screens: {
        '2xl': '1400px',
      },
    },
    extend: {
      colors: {
        border: 'hsl(var(--finsync-muted-foreground) / 0.2)',
        input: 'hsl(var(--finsync-muted-foreground) / 0.3)',
        ring: 'hsl(var(--finsync-primary))',
        background: 'hsl(var(--finsync-background))',
        foreground: 'hsl(var(--finsync-foreground))',
        primary: {
          DEFAULT: 'hsl(var(--finsync-primary))',
          foreground: 'hsl(var(--finsync-background))', 
        },
        secondary: {
          DEFAULT: 'hsl(var(--finsync-secondary))',
          foreground: 'hsl(var(--finsync-background))', 
        },
        destructive: {
          DEFAULT: 'hsl(var(--finsync-error))',
          foreground: 'hsl(var(--finsync-background))', 
        },
        muted: {
          DEFAULT: 'hsl(var(--finsync-muted))',
          foreground: 'hsl(var(--finsync-muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--finsync-accent))',
          foreground: 'hsl(var(--finsync-foreground))', 
        },
        popover: {
          DEFAULT: 'hsl(var(--finsync-background))',
          foreground: 'hsl(var(--finsync-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--finsync-background))', 
          foreground: 'hsl(var(--finsync-foreground))',
        },
      },
      borderRadius: {
        lg: 'var(--finsync-radius-lg)',
        md: 'var(--finsync-radius-md)',
        sm: 'var(--finsync-radius-sm)',
      },
      keyframes: {
        'accordion-down': {
          from: { height: '0' },
          to: { height: 'var(--radix-accordion-content-height)' },
        },
        'accordion-up': {
          from: { height: 'var(--radix-accordion-content-height)' },
          to: { height: '0' },
        },
        // beam-animate should be defined in index.css, but if needed in Tailwind context:
        // 'beam-animate': {
        //   '0%': { backgroundPosition: '0% center' },
        //   '100%': { backgroundPosition: '200% center' },
        // },
      },
      animation: {
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out',
        // 'border-beam': 'beam-animate 6s linear infinite', // if using Tailwind for beam
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
};

