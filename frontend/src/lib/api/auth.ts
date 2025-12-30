/**
 * Authentication API functions
 */
import type { User, LoginCredentials, RegisterData, AuthToken } from '@/types';
import { fetchApi, setStoredToken, clearStoredToken } from './client';

export async function login(credentials: LoginCredentials): Promise<AuthToken> {
  const token = await fetchApi<AuthToken>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(credentials),
  });
  setStoredToken(token.access_token);
  return token;
}

export async function register(data: RegisterData): Promise<User> {
  return fetchApi<User>('/auth/register', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function getCurrentUser(): Promise<User> {
  return fetchApi<User>('/auth/me', {}, true);
}

export async function updateProfile(updates: { display_name?: string }): Promise<User> {
  return fetchApi<User>('/auth/me', {
    method: 'PATCH',
    body: JSON.stringify(updates),
  }, true);
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  await fetchApi('/auth/change-password', {
    method: 'POST',
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  }, true);
}

export async function logout(): Promise<void> {
  try {
    await fetchApi('/auth/logout', { method: 'POST' }, true);
  } finally {
    clearStoredToken();
  }
}
