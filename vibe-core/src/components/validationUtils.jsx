/*
 * Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
 * Author: Christopher Niven
 */
/**
 * Validation utilities for PublicSignup component
 */

/**
 * Validate email format
 */
export const validateEmail = (email) => {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
};

/**
 * Validate phone number (basic international format)
 */
export const validatePhone = (phone) => {
  // Remove all non-numeric characters except +
  const cleaned = phone.replace(/[^\d+]/g, '');
  // Should have at least 10 digits
  return cleaned.length >= 10;
};

/**
 * Validate password strength
 */
export const validatePassword = (password) => {
  const errors = [];
  
  if (password.length < 8) {
    errors.push('Password must be at least 8 characters');
  }
  
  if (!/[A-Z]/.test(password)) {
    errors.push('Password must contain at least one uppercase letter');
  }
  
  if (!/[a-z]/.test(password)) {
    errors.push('Password must contain at least one lowercase letter');
  }
  
  if (!/[0-9]/.test(password)) {
    errors.push('Password must contain at least one number');
  }
  
  if (!/[!@#$%^&*(),.?":{}|<>]/.test(password)) {
    errors.push('Password should contain at least one special character (recommended)');
  }
  
  return {
    valid: errors.length === 0 || (errors.length === 1 && errors[0].includes('recommended')),
    errors,
    strength: getPasswordStrength(password)
  };
};

/**
 * Get password strength score
 */
const getPasswordStrength = (password) => {
  let strength = 0;
  
  if (password.length >= 8) strength++;
  if (password.length >= 12) strength++;
  if (/[A-Z]/.test(password)) strength++;
  if (/[a-z]/.test(password)) strength++;
  if (/[0-9]/.test(password)) strength++;
  if (/[!@#$%^&*(),.?":{}|<>]/.test(password)) strength++;
  
  if (strength <= 2) return 'weak';
  if (strength <= 4) return 'medium';
  return 'strong';
};

/**
 * Validate credit card number using Luhn algorithm
 */
export const validateCardNumber = (cardNumber) => {
  // Remove spaces and dashes
  const cleaned = cardNumber.replace(/[\s-]/g, '');
  
  // Check if it's all digits
  if (!/^\d+$/.test(cleaned)) {
    return { valid: false, error: 'Card number must contain only digits' };
  }
  
  // Check length
  if (cleaned.length < 13 || cleaned.length > 19) {
    return { valid: false, error: 'Invalid card number length' };
  }
  
  // Luhn algorithm
  let sum = 0;
  let isEven = false;
  
  for (let i = cleaned.length - 1; i >= 0; i--) {
    let digit = parseInt(cleaned[i], 10);
    
    if (isEven) {
      digit *= 2;
      if (digit > 9) {
        digit -= 9;
      }
    }
    
    sum += digit;
    isEven = !isEven;
  }
  
  const isValid = sum % 10 === 0;
  
  return {
    valid: isValid,
    error: isValid ? null : 'Invalid card number',
    cardType: detectCardType(cleaned)
  };
};

/**
 * Detect card type from card number
 */
export const detectCardType = (cardNumber) => {
  const cleaned = cardNumber.replace(/[\s-]/g, '');
  
  if (/^4/.test(cleaned)) return 'visa';
  if (/^5[1-5]/.test(cleaned)) return 'mastercard';
  if (/^3[47]/.test(cleaned)) return 'amex';
  if (/^6(?:011|5)/.test(cleaned)) return 'discover';
  if (/^35/.test(cleaned)) return 'jcb';
  if (/^30[0-5]/.test(cleaned)) return 'diners';
  
  return 'unknown';
};

/**
 * Validate CVV
 */
export const validateCVV = (cvv, cardType = 'unknown') => {
  if (!/^\d+$/.test(cvv)) {
    return { valid: false, error: 'CVV must contain only digits' };
  }
  
  // Amex has 4 digits, others have 3
  const expectedLength = cardType === 'amex' ? 4 : 3;
  
  if (cvv.length < 3 || cvv.length > 4) {
    return { valid: false, error: `CVV must be ${expectedLength} digits` };
  }
  
  return { valid: true, error: null };
};

/**
 * Validate expiry date
 */
export const validateExpiry = (month, year) => {
  const monthNum = parseInt(month, 10);
  let yearNum = parseInt(year, 10);
  
  if (isNaN(monthNum) || monthNum < 1 || monthNum > 12) {
    return { valid: false, error: 'Invalid month' };
  }
  
  if (isNaN(yearNum)) {
    return { valid: false, error: 'Invalid year' };
  }
  
  // Convert 2-digit year to 4-digit
  if (yearNum < 100) {
    yearNum += 2000;
  }
  
  const now = new Date();
  const currentYear = now.getFullYear();
  const currentMonth = now.getMonth() + 1;
  
  if (yearNum < currentYear) {
    return { valid: false, error: 'Card is expired' };
  }
  
  if (yearNum === currentYear && monthNum < currentMonth) {
    return { valid: false, error: 'Card is expired' };
  }
  
  // Check if expiry is too far in future (10 years)
  if (yearNum > currentYear + 10) {
    return { valid: false, error: 'Invalid expiry date' };
  }
  
  return { valid: true, error: null };
};

/**
 * Format card number with spaces
 */
export const formatCardNumber = (value) => {
  const cleaned = value.replace(/\D/g, '');
  const cardType = detectCardType(cleaned);
  
  // Amex format: 4-6-5
  if (cardType === 'amex') {
    const match = cleaned.match(/(\d{0,4})(\d{0,6})(\d{0,5})/);
    if (!match) return cleaned;
    return [match[1], match[2], match[3]].filter(Boolean).join(' ');
  }
  
  // Standard format: 4-4-4-4
  const match = cleaned.match(/(\d{0,4})(\d{0,4})(\d{0,4})(\d{0,4})/);
  if (!match) return cleaned;
  return [match[1], match[2], match[3], match[4]].filter(Boolean).join(' ');
};

/**
 * Format phone number
 */
export const formatPhoneNumber = (value) => {
  // Remove all non-numeric characters except +
  const cleaned = value.replace(/[^\d+]/g, '');
  
  // If starts with +, format as international
  if (cleaned.startsWith('+')) {
    return cleaned;
  }
  
  // US format: (XXX) XXX-XXXX
  const match = cleaned.match(/^(\d{0,3})(\d{0,3})(\d{0,4})$/);
  if (!match) return cleaned;
  
  if (match[3]) {
    return `(${match[1]}) ${match[2]}-${match[3]}`;
  } else if (match[2]) {
    return `(${match[1]}) ${match[2]}`;
  } else if (match[1]) {
    return `(${match[1]}`;
  }
  
  return cleaned;
};

/**
 * Validate postal code based on country
 */
export const validatePostalCode = (postalCode, country) => {
  if (!postalCode) {
    return { valid: false, error: 'Postal code is required' };
  }
  
  switch (country) {
    case 'US':
      // US ZIP: 12345 or 12345-6789
      if (!/^\d{5}(-\d{4})?$/.test(postalCode)) {
        return { valid: false, error: 'Invalid US ZIP code' };
      }
      break;
    case 'CA':
      // Canada: A1A 1A1
      if (!/^[A-Za-z]\d[A-Za-z]\s?\d[A-Za-z]\d$/.test(postalCode)) {
        return { valid: false, error: 'Invalid Canadian postal code' };
      }
      break;
    case 'GB':
      // UK: Various formats
      if (!/^[A-Z]{1,2}\d{1,2}\s?\d[A-Z]{2}$/i.test(postalCode)) {
        return { valid: false, error: 'Invalid UK postal code' };
      }
      break;
    default:
      // Generic validation - at least 3 characters
      if (postalCode.length < 3) {
        return { valid: false, error: 'Postal code too short' };
      }
  }
  
  return { valid: true, error: null };
};

/**
 * Validate state/province code
 */
export const validateState = (state, country) => {
  if (!state) {
    return { valid: false, error: 'State/Province is required' };
  }
  
  // For US, validate 2-letter state codes
  if (country === 'US') {
    const usStates = [
      'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
      'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
      'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
      'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
      'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
      'DC'
    ];
    
    if (!usStates.includes(state.toUpperCase())) {
      return { valid: false, error: 'Invalid US state code' };
    }
  }
  
  return { valid: true, error: null };
};

/**
 * Sanitize input to prevent XSS
 */
export const sanitizeInput = (input) => {
  if (typeof input !== 'string') return input;
  
  return input
    .replace(/[<>]/g, '') // Remove < and >
    .trim();
};

/**
 * Validate company name
 */
export const validateCompanyName = (name) => {
  if (!name || name.trim().length === 0) {
    return { valid: false, error: 'Company name is required' };
  }
  
  if (name.length < 2) {
    return { valid: false, error: 'Company name too short' };
  }
  
  if (name.length > 100) {
    return { valid: false, error: 'Company name too long (max 100 characters)' };
  }
  
  return { valid: true, error: null };
};

/**
 * Validate address
 */
export const validateAddress = (address) => {
  if (!address || address.trim().length === 0) {
    return { valid: false, error: 'Address is required' };
  }
  
  if (address.length < 5) {
    return { valid: false, error: 'Address too short' };
  }
  
  return { valid: true, error: null };
};

/**
 * Validate city
 */
export const validateCity = (city) => {
  if (!city || city.trim().length === 0) {
    return { valid: false, error: 'City is required' };
  }
  
  if (city.length < 2) {
    return { valid: false, error: 'City name too short' };
  }
  
  return { valid: true, error: null };
};

/**
 * Get all US states for dropdown
 */
export const getUSStates = () => {
  return [
    { code: 'AL', name: 'Alabama' },
    { code: 'AK', name: 'Alaska' },
    { code: 'AZ', name: 'Arizona' },
    { code: 'AR', name: 'Arkansas' },
    { code: 'CA', name: 'California' },
    { code: 'CO', name: 'Colorado' },
    { code: 'CT', name: 'Connecticut' },
    { code: 'DE', name: 'Delaware' },
    { code: 'FL', name: 'Florida' },
    { code: 'GA', name: 'Georgia' },
    { code: 'HI', name: 'Hawaii' },
    { code: 'ID', name: 'Idaho' },
    { code: 'IL', name: 'Illinois' },
    { code: 'IN', name: 'Indiana' },
    { code: 'IA', name: 'Iowa' },
    { code: 'KS', name: 'Kansas' },
    { code: 'KY', name: 'Kentucky' },
    { code: 'LA', name: 'Louisiana' },
    { code: 'ME', name: 'Maine' },
    { code: 'MD', name: 'Maryland' },
    { code: 'MA', name: 'Massachusetts' },
    { code: 'MI', name: 'Michigan' },
    { code: 'MN', name: 'Minnesota' },
    { code: 'MS', name: 'Mississippi' },
    { code: 'MO', name: 'Missouri' },
    { code: 'MT', name: 'Montana' },
    { code: 'NE', name: 'Nebraska' },
    { code: 'NV', name: 'Nevada' },
    { code: 'NH', name: 'New Hampshire' },
    { code: 'NJ', name: 'New Jersey' },
    { code: 'NM', name: 'New Mexico' },
    { code: 'NY', name: 'New York' },
    { code: 'NC', name: 'North Carolina' },
    { code: 'ND', name: 'North Dakota' },
    { code: 'OH', name: 'Ohio' },
    { code: 'OK', name: 'Oklahoma' },
    { code: 'OR', name: 'Oregon' },
    { code: 'PA', name: 'Pennsylvania' },
    { code: 'RI', name: 'Rhode Island' },
    { code: 'SC', name: 'South Carolina' },
    { code: 'SD', name: 'South Dakota' },
    { code: 'TN', name: 'Tennessee' },
    { code: 'TX', name: 'Texas' },
    { code: 'UT', name: 'Utah' },
    { code: 'VT', name: 'Vermont' },
    { code: 'VA', name: 'Virginia' },
    { code: 'WA', name: 'Washington' },
    { code: 'WV', name: 'West Virginia' },
    { code: 'WI', name: 'Wisconsin' },
    { code: 'WY', name: 'Wyoming' },
    { code: 'DC', name: 'District of Columbia' }
  ];
};

/**
 * Get list of countries
 */
export const getCountries = () => {
  return [
    { code: 'US', name: 'United States' },
    { code: 'CA', name: 'Canada' },
    { code: 'GB', name: 'United Kingdom' },
    { code: 'AU', name: 'Australia' },
    { code: 'NZ', name: 'New Zealand' },
    { code: 'IE', name: 'Ireland' },
    { code: 'DE', name: 'Germany' },
    { code: 'FR', name: 'France' },
    { code: 'ES', name: 'Spain' },
    { code: 'IT', name: 'Italy' },
    { code: 'JP', name: 'Japan' },
    { code: 'CN', name: 'China' },
    { code: 'IN', name: 'India' },
    { code: 'BR', name: 'Brazil' },
    { code: 'MX', name: 'Mexico' }
  ];
};
