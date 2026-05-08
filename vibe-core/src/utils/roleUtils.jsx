/*
 * Copyright (c) 2026 Vibe For Everyone, LLC. All rights reserved.
 * Author: Christopher Niven
 */
/**
 * roleUtils.js
 *
 * Utility for checking role assignments client-side.
 *
 * Roles are sourced from the JWT payload held in AuthContext memory.
 * They are never read from localStorage.
 *
 * Usage in a React component:
 *   import { useRoles } from '../utils/roleUtils';
 *   const { isRoleAssigned, roles } = useRoles();
 *   if (isRoleAssigned('Admin')) { ... }
 *
 * Usage outside a React component (e.g. a utility function):
 *   import { isRoleAssignedFromToken } from '../utils/roleUtils';
 *   if (isRoleAssignedFromToken('Invoicing')) { ... }
 */

import { useAuth }        from '../context/AuthContext';
import { getAccessToken } from '../context/AuthContext';

/**
 * useRoles — React hook version.
 * Use this inside functional components.
 */
export const useRoles = () => {
  const { user } = useAuth();
  const roles    = user?.roles || [];

  const isRoleAssigned = (roleName) => {
    if (!roleName || !roles.length) return false;
    return roles.some(
      r => (typeof r === 'string' ? r : r?.role_desc)?.toLowerCase()
            === roleName.toLowerCase()
    );
  };

  return { roles, isRoleAssigned };
};

/**
 * isRoleAssignedFromToken — non-hook version.
 * Use this outside React components (utility functions, guards, etc.)
 * Decodes the current access token without verifying the signature
 * (verification happens server-side on every API call).
 */
export const isRoleAssignedFromToken = (roleName) => {
  const token = getAccessToken();
  if (!token || token === 'jwt-not-available') return false;

  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    const roles   = payload.roles || [];
    if (!roleName || !roles.length) return false;
    return roles.some(
      r => (typeof r === 'string' ? r : r?.role_desc)?.toLowerCase()
            === roleName.toLowerCase()
    );
  } catch {
    return false;
  }
};

/**
 * getRolesFromToken — returns the full roles array from the current token.
 * Non-hook version.
 */
export const getRolesFromToken = () => {
  const token = getAccessToken();
  if (!token || token === 'jwt-not-available') return [];
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.roles || [];
  } catch {
    return [];
  }
};
