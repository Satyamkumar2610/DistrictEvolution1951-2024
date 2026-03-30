'use client';

/**
 * Card Component for I-ASCAP Rainfall Analytics Platform
 * 
 * A flexible container component for content grouping with multiple variants,
 * padding options, and interactive states. Uses semantic HTML based on context.
 */

import React, { forwardRef } from 'react';
import { cn } from '../utils/cn';

// ============================================================================
// Types
// ============================================================================

export interface CardProps extends React.HTMLAttributes<HTMLElement> {
  children: React.ReactNode;
  variant?: 'default' | 'elevated' | 'outlined' | 'ghost';
  padding?: 'none' | 'sm' | 'md' | 'lg';
  hoverable?: boolean;
  clickable?: boolean;
  onClick?: () => void;
  as?: 'div' | 'article' | 'section';
}

// ============================================================================
// Card Component
// ============================================================================

export const Card = forwardRef<HTMLElement, CardProps>(
  (
    {
      children,
      variant = 'default',
      padding = 'md',
      hoverable = false,
      clickable = false,
      onClick,
      as: Component = 'div',
      className,
      ...props
    },
    ref
  ) => {
    // Determine if card is interactive
    const isInteractive = clickable || !!onClick;

    // Base styles
    const baseStyles = cn(
      'rounded-[var(--radius-lg)]',
      'transition-all duration-200',
      'w-full'
    );

    // Variant styles
    const variantStyles = {
      default: cn(
        'bg-[var(--color-background-primary)]',
        'border border-[var(--color-border-default)]'
      ),
      elevated: cn(
        'bg-[var(--color-background-primary)]',
        'shadow-[var(--shadow-md)]',
        hoverable && 'hover:shadow-[var(--shadow-lg)]'
      ),
      outlined: cn(
        'bg-transparent',
        'border-2 border-[var(--color-border-default)]',
        hoverable && 'hover:border-[var(--color-border-hover)]'
      ),
      ghost: cn(
        'bg-transparent'
      ),
    };

    // Padding styles
    const paddingStyles = {
      none: '',
      sm: 'p-3',
      md: 'p-4',
      lg: 'p-6',
    };

    // Hoverable styles
    const hoverStyles = hoverable && cn(
      'hover:bg-[var(--color-background-secondary)]',
      variant === 'elevated' && 'hover:translate-y-[-2px]'
    );

    // Clickable/Interactive styles
    const interactiveStyles = isInteractive && cn(
      'cursor-pointer',
      'focus:outline-none focus:ring-2 focus:ring-[var(--color-primary-500)] focus:ring-offset-2',
      'active:scale-[0.98]'
    );

    // Combine all styles
    const cardClasses = cn(
      baseStyles,
      variantStyles[variant],
      paddingStyles[padding],
      hoverStyles,
      interactiveStyles,
      className
    );

    // Props for interactive cards
    const interactiveProps = isInteractive
      ? {
        role: onClick ? 'button' : undefined,
        tabIndex: 0,
        onClick,
        onKeyDown: (e: React.KeyboardEvent) => {
          if (onClick && (e.key === 'Enter' || e.key === ' ')) {
            e.preventDefault();
            onClick();
          }
        },
      }
      : {};

    return (
      <Component
        ref={ref as React.Ref<HTMLDivElement>}
        className={cardClasses}
        {...interactiveProps}
        {...props}
      >
        {children}
      </Component>
    );
  }
);

Card.displayName = 'Card';
