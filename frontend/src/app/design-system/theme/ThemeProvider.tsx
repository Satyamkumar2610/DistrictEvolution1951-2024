'use client';

/**
 * ThemeProvider Component for I-ASCAP Rainfall Analytics Platform
 * 
 * Provides theme context to the entire application with:
 * - Light/dark mode switching
 * - localStorage persistence
 * - System preference detection
 * - Dynamic CSS variable application
 * - SSR-safe implementation for Next.js
 */

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { ThemeConfig, getThemeConfig, applyCSSVariables } from './config';

// ============================================================================
// Types
// ============================================================================

export interface ThemeProviderProps {
  children: React.ReactNode;
  defaultTheme?: 'light' | 'dark';
  storageKey?: string;
}

export interface ThemeContextValue {
  theme: 'light' | 'dark';
  setTheme: (theme: 'light' | 'dark') => void;
  toggleTheme: () => void;
  config: ThemeConfig;
}

// ============================================================================
// Context
// ============================================================================

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

// ============================================================================
// Constants
// ============================================================================

const DEFAULT_STORAGE_KEY = 'i-ascap-theme';
const THEME_ATTRIBUTE = 'data-theme';

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get system theme preference
 */
function getSystemTheme(): 'light' | 'dark' {
  if (typeof window === 'undefined') return 'light';

  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

/**
 * Get stored theme from localStorage
 */
function getStoredTheme(storageKey: string): 'light' | 'dark' | null {
  if (typeof window === 'undefined') return null;

  try {
    const stored = localStorage.getItem(storageKey);
    if (stored === 'light' || stored === 'dark') {
      return stored;
    }
  } catch (error) {
    console.warn('Failed to read theme from localStorage:', error);
  }

  return null;
}

/**
 * Store theme in localStorage
 */
function storeTheme(storageKey: string, theme: 'light' | 'dark'): void {
  if (typeof window === 'undefined') return;

  try {
    localStorage.setItem(storageKey, theme);
  } catch (error) {
    console.warn('Failed to store theme in localStorage:', error);
  }
}

/**
 * Get initial theme (stored > system > default)
 */
function getInitialTheme(
  storageKey: string,
  defaultTheme?: 'light' | 'dark'
): 'light' | 'dark' {
  const stored = getStoredTheme(storageKey);
  if (stored) return stored;

  if (defaultTheme) return defaultTheme;

  return getSystemTheme();
}

// ============================================================================
// ThemeProvider Component
// ============================================================================

export function ThemeProvider({
  children,
  defaultTheme,
  storageKey = DEFAULT_STORAGE_KEY,
}: ThemeProviderProps) {
  // Initialize theme state with SSR-safe approach
  const [theme, setThemeState] = useState<'light' | 'dark'>(() => {
    // During SSR, use defaultTheme or 'light'
    if (typeof window === 'undefined') {
      return defaultTheme || 'light';
    }

    // On client, get initial theme from storage/system/default
    return getInitialTheme(storageKey, defaultTheme);
  });

  const [, setMounted] = useState(false);

  // Get current theme config
  const config = getThemeConfig(theme);

  /**
   * Set theme and persist to localStorage
   */
  const setTheme = useCallback((newTheme: 'light' | 'dark') => {
    setThemeState(newTheme);
    storeTheme(storageKey, newTheme);

    // Update document attribute for CSS targeting
    if (typeof window !== 'undefined') {
      document.documentElement.setAttribute(THEME_ATTRIBUTE, newTheme);
    }
  }, [storageKey]);

  /**
   * Toggle between light and dark themes
   */
  const toggleTheme = useCallback(() => {
    setTheme(theme === 'light' ? 'dark' : 'light');
  }, [theme, setTheme]);

  // Apply CSS variables when theme changes
  useEffect(() => {
    if (typeof window === 'undefined') return;

    applyCSSVariables(config);
    document.documentElement.setAttribute(THEME_ATTRIBUTE, theme);
  }, [theme, config]);

  // Handle system theme preference changes
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

    const handleChange = (e: MediaQueryListEvent) => {
      // Only update if no stored preference exists
      const stored = getStoredTheme(storageKey);
      if (!stored) {
        const systemTheme = e.matches ? 'dark' : 'light';
        setThemeState(systemTheme);
      }
    };

    // Modern browsers
    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', handleChange);
      return () => mediaQuery.removeEventListener('change', handleChange);
    }
    // Legacy browsers
    else if (mediaQuery.addListener) {
      mediaQuery.addListener(handleChange);
      return () => mediaQuery.removeListener(handleChange);
    }
  }, [storageKey]);

  // Set mounted flag after hydration
  useEffect(() => {
    setMounted(true);
  }, []);

  // Prevent flash of unstyled content during SSR
  // Render children immediately but apply theme after mount
  const contextValue: ThemeContextValue = {
    theme,
    setTheme,
    toggleTheme,
    config,
  };

  return (
    <ThemeContext.Provider value={contextValue}>
      {children}
    </ThemeContext.Provider>
  );
}

// ============================================================================
// Hook
// ============================================================================

/**
 * Hook to access theme context
 * 
 * @throws Error if used outside ThemeProvider
 */
export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);

  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }

  return context;
}

// ============================================================================
// Theme Initialization Script
// ============================================================================

/**
 * Script to prevent flash of unstyled content (FOUC)
 * This should be injected in the document head before any content renders
 * 
 * Usage in Next.js app/layout.tsx:
 * <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
 */
export const themeInitScript = `
(function() {
  try {
    const storageKey = '${DEFAULT_STORAGE_KEY}';
    const stored = localStorage.getItem(storageKey);
    const theme = stored || 
      (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    document.documentElement.setAttribute('${THEME_ATTRIBUTE}', theme);
  } catch (e) {
    console.warn('Failed to initialize theme:', e);
  }
})();
`;
