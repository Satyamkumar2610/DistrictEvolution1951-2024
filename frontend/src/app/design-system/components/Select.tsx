'use client';

/**
 * Select Component for I-ASCAP Rainfall Analytics Platform
 * 
 * An accessible dropdown selection component with keyboard navigation and search capability.
 * Supports label, error states, disabled options, and screen reader announcements.
 */

import React, { forwardRef, useId, useState, useRef, useEffect } from 'react';
import { cn } from '../utils/cn';

// ============================================================================
// Types
// ============================================================================

export interface SelectOption<T = string> {
  value: T;
  label: string;
  disabled?: boolean;
}

export interface SelectProps<T = string> {
  options: SelectOption<T>[];
  value: T;
  onChange: (value: T) => void;
  label?: string;
  placeholder?: string;
  error?: string;
  isDisabled?: boolean;
  isSearchable?: boolean;
}

// ============================================================================
// Select Component
// ============================================================================

function SelectInner<T = string>(
  {
    options,
    value,
    onChange,
    label,
    placeholder = 'Select an option',
    error,
    isDisabled = false,
    isSearchable = false,
  }: SelectProps<T>,
  ref: React.ForwardedRef<HTMLButtonElement>
) {
  // Generate unique IDs for accessibility
  const generatedId = useId();
  const selectId = `select-${generatedId}`;
  const labelId = `${selectId}-label`;
  const errorId = `${selectId}-error`;
  const listboxId = `${selectId}-listbox`;

  // State management
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const [announcementText, setAnnouncementText] = useState('');

  // Refs
  const containerRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const listboxRef = useRef<HTMLUListElement>(null);

  // Find selected option
  const selectedOption = options.find((opt) => opt.value === value);

  // Filter options based on search query
  const filteredOptions = isSearchable && searchQuery
    ? options.filter((opt) =>
      opt.label.toLowerCase().includes(searchQuery.toLowerCase())
    )
    : options;

  // Determine if select is in error state
  const hasError = !!error;

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
        setSearchQuery('');
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => {
        document.removeEventListener('mousedown', handleClickOutside);
      };
    }
  }, [isOpen]);

  // Focus search input when dropdown opens
  useEffect(() => {
    if (isOpen && isSearchable && searchInputRef.current) {
      searchInputRef.current.focus();
    }
  }, [isOpen, isSearchable]);

  // Reset highlighted index when filtered options change
  useEffect(() => {
    setHighlightedIndex(-1);
  }, [searchQuery]);

  // Announce changes to screen readers
  const announce = (text: string) => {
    setAnnouncementText(text);
    setTimeout(() => setAnnouncementText(''), 100);
  };

  // Handle option selection
  const handleSelect = (option: SelectOption<T>) => {
    if (option.disabled) return;

    onChange(option.value);
    setIsOpen(false);
    setSearchQuery('');
    announce(`${option.label} selected`);
  };

  // Handle keyboard navigation
  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (isDisabled) return;

    switch (event.key) {
      case 'Enter':
      case ' ':
        if (!isOpen) {
          event.preventDefault();
          setIsOpen(true);
          announce('Dropdown opened');
        } else if (highlightedIndex >= 0 && highlightedIndex < filteredOptions.length) {
          event.preventDefault();
          handleSelect(filteredOptions[highlightedIndex]);
        }
        break;

      case 'Escape':
        if (isOpen) {
          event.preventDefault();
          setIsOpen(false);
          setSearchQuery('');
          announce('Dropdown closed');
        }
        break;

      case 'ArrowDown':
        event.preventDefault();
        if (!isOpen) {
          setIsOpen(true);
          announce('Dropdown opened');
        } else {
          const nextIndex = highlightedIndex < filteredOptions.length - 1
            ? highlightedIndex + 1
            : 0;
          setHighlightedIndex(nextIndex);

          // Scroll into view
          const optionElement = listboxRef.current?.children[nextIndex] as HTMLElement;
          optionElement?.scrollIntoView({ block: 'nearest' });

          announce(filteredOptions[nextIndex].label);
        }
        break;

      case 'ArrowUp':
        event.preventDefault();
        if (!isOpen) {
          setIsOpen(true);
          announce('Dropdown opened');
        } else {
          const prevIndex = highlightedIndex > 0
            ? highlightedIndex - 1
            : filteredOptions.length - 1;
          setHighlightedIndex(prevIndex);

          // Scroll into view
          const optionElement = listboxRef.current?.children[prevIndex] as HTMLElement;
          optionElement?.scrollIntoView({ block: 'nearest' });

          announce(filteredOptions[prevIndex].label);
        }
        break;

      case 'Home':
        if (isOpen) {
          event.preventDefault();
          setHighlightedIndex(0);
          const optionElement = listboxRef.current?.children[0] as HTMLElement;
          optionElement?.scrollIntoView({ block: 'nearest' });
          announce(filteredOptions[0].label);
        }
        break;

      case 'End':
        if (isOpen) {
          event.preventDefault();
          const lastIndex = filteredOptions.length - 1;
          setHighlightedIndex(lastIndex);
          const optionElement = listboxRef.current?.children[lastIndex] as HTMLElement;
          optionElement?.scrollIntoView({ block: 'nearest' });
          announce(filteredOptions[lastIndex].label);
        }
        break;

      default:
        break;
    }
  };

  // Handle search input change
  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const query = event.target.value;
    setSearchQuery(query);

    if (query) {
      announce(`${filteredOptions.length} options available`);
    }
  };

  // Toggle dropdown
  const handleToggle = () => {
    if (isDisabled) return;

    const newIsOpen = !isOpen;
    setIsOpen(newIsOpen);

    if (!newIsOpen) {
      setSearchQuery('');
    }

    announce(newIsOpen ? 'Dropdown opened' : 'Dropdown closed');
  };

  // Styles
  const labelStyles = cn(
    'block',
    'text-sm',
    'font-medium',
    'text-[var(--color-text-primary)]',
    'mb-1.5',
    isDisabled && 'opacity-50 cursor-not-allowed'
  );

  const buttonStyles = cn(
    'w-full',
    'px-3 py-2',
    'text-base',
    'font-normal',
    'text-left',
    'bg-[var(--color-background-primary)]',
    'border border-[var(--color-border-default)]',
    'rounded-[var(--radius-md)]',
    'transition-all duration-200',
    'focus:outline-none focus:ring-2 focus:ring-offset-0',
    'flex items-center justify-between',
    hasError
      ? cn(
        'border-[var(--color-error-500)]',
        'focus:border-[var(--color-error-500)]',
        'focus:ring-[var(--color-error-500)]'
      )
      : cn(
        'hover:border-[var(--color-border-hover)]',
        'focus:border-[var(--color-border-focus)]',
        'focus:ring-[var(--color-primary-500)]'
      ),
    isDisabled && 'opacity-50 cursor-not-allowed bg-[var(--color-background-secondary)]',
    !isDisabled && 'cursor-pointer'
  );

  const dropdownStyles = cn(
    'absolute',
    'z-50',
    'w-full',
    'mt-1',
    'bg-[var(--color-background-primary)]',
    'border border-[var(--color-border-default)]',
    'rounded-[var(--radius-md)]',
    'shadow-[var(--shadow-lg)]',
    'max-h-60',
    'overflow-hidden',
    'animate-in fade-in-0 zoom-in-95'
  );

  const searchInputStyles = cn(
    'w-full',
    'px-3 py-2',
    'text-base',
    'border-b border-[var(--color-border-default)]',
    'focus:outline-none',
    'bg-[var(--color-background-primary)]',
    'text-[var(--color-text-primary)]',
    'placeholder:text-[var(--color-text-tertiary)]'
  );

  const listboxStyles = cn(
    'max-h-48',
    'overflow-y-auto',
    'py-1'
  );

  const optionStyles = (option: SelectOption<T>, index: number) => cn(
    'px-3 py-2',
    'text-base',
    'cursor-pointer',
    'transition-colors duration-150',
    'flex items-center justify-between',
    option.disabled
      ? 'opacity-50 cursor-not-allowed'
      : cn(
        'hover:bg-[var(--color-background-secondary)]',
        highlightedIndex === index && 'bg-[var(--color-background-secondary)]',
        option.value === value && 'bg-[var(--color-primary-50)] text-[var(--color-primary-700)]'
      )
  );

  const errorTextStyles = cn(
    'mt-1.5',
    'text-sm',
    'text-[var(--color-error-600)]',
    'flex items-start gap-1'
  );

  return (
    <div className="w-full" ref={containerRef}>
      {/* Label */}
      {label && (
        <label id={labelId} htmlFor={selectId} className={labelStyles}>
          {label}
        </label>
      )}

      {/* Select Button */}
      <button
        ref={ref}
        id={selectId}
        type="button"
        role="combobox"
        aria-expanded={isOpen}
        aria-haspopup="listbox"
        aria-controls={listboxId}
        aria-labelledby={label ? labelId : undefined}
        aria-invalid={hasError}
        aria-describedby={error ? errorId : undefined}
        disabled={isDisabled}
        className={buttonStyles}
        onClick={handleToggle}
        onKeyDown={handleKeyDown}
      >
        <span className={cn(!selectedOption && 'text-[var(--color-text-tertiary)]')}>
          {selectedOption ? selectedOption.label : placeholder}
        </span>

        {/* Chevron Icon */}
        <svg
          className={cn(
            'w-5 h-5',
            'text-[var(--color-text-tertiary)]',
            'transition-transform duration-200',
            isOpen && 'rotate-180'
          )}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className={dropdownStyles}>
          {/* Search Input */}
          {isSearchable && (
            <input
              ref={searchInputRef}
              type="text"
              role="searchbox"
              aria-label="Search options"
              placeholder="Search..."
              value={searchQuery}
              onChange={handleSearchChange}
              className={searchInputStyles}
              onKeyDown={(e) => {
                if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
                  e.preventDefault();
                  handleKeyDown(e as any /* eslint-disable-line @typescript-eslint/no-explicit-any */);
                } else if (e.key === 'Escape') {
                  setIsOpen(false);
                  setSearchQuery('');
                }
              }}
            />
          )}

          {/* Options List */}
          <ul
            ref={listboxRef}
            id={listboxId}
            role="listbox"
            aria-labelledby={label ? labelId : undefined}
            className={listboxStyles}
          >
            {filteredOptions.length === 0 ? (
              <li
                role="option"
                aria-selected={false}
                className="px-3 py-2 text-base text-[var(--color-text-tertiary)]"
              >
                No options found
              </li>
            ) : (
              filteredOptions.map((option, index) => (
                <li
                  key={String(option.value)}
                  role="option"
                  aria-selected={option.value === value}
                  aria-disabled={option.disabled}
                  className={optionStyles(option, index)}
                  onClick={() => !option.disabled && handleSelect(option)}
                  onMouseEnter={() => !option.disabled && setHighlightedIndex(index)}
                >
                  <span>{option.label}</span>

                  {/* Checkmark for selected option */}
                  {option.value === value && (
                    <svg
                      className="w-5 h-5 text-[var(--color-primary-600)]"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                      aria-hidden="true"
                    >
                      <path
                        fillRule="evenodd"
                        d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                        clipRule="evenodd"
                      />
                    </svg>
                  )}
                </li>
              ))
            )}
          </ul>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div id={errorId} className={errorTextStyles} role="alert" aria-live="polite">
          <svg
            className="w-4 h-4 mt-0.5 flex-shrink-0"
            fill="currentColor"
            viewBox="0 0 20 20"
            aria-hidden="true"
          >
            <path
              fillRule="evenodd"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
              clipRule="evenodd"
            />
          </svg>
          <span>{error}</span>
        </div>
      )}

      {/* Screen Reader Announcements */}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {announcementText}
      </div>
    </div>
  );
}

// Export with proper generic typing
export const Select = forwardRef(SelectInner) as <T = string>(
  props: SelectProps<T> & { ref?: React.ForwardedRef<HTMLButtonElement> }
) => ReturnType<typeof SelectInner>;
