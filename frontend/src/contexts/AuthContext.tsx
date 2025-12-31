'use client';

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  useRef,
  type ReactNode,
} from 'react';
import { useRouter } from 'next/navigation';
import type { User, LoginCredentials, RegisterData } from '@/types';
import {
  login as apiLogin,
  register as apiRegister,
  logout as apiLogout,
  getCurrentUser,
  getStoredToken,
  clearStoredToken,
  setStoredToken,
} from '@/lib/api';

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  isOAuthPending: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  handleOAuthToken: (token: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isOAuthPending, setIsOAuthPending] = useState(false);
  const router = useRouter();
  const initRef = useRef(false);

  const refreshUser = useCallback(async () => {
    const token = getStoredToken();
    if (!token) {
      setUser(null);
      setIsLoading(false);
      return;
    }

    try {
      const userData = await getCurrentUser();
      setUser(userData);
    } catch (error) {
      // Token is invalid or expired
      clearStoredToken();
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Handle OAuth token - stores token and refreshes user in one atomic operation
  const handleOAuthToken = useCallback(async (token: string) => {
    setIsOAuthPending(true);
    setIsLoading(true);
    try {
      // Store the token
      setStoredToken(token);
      // Small delay to ensure localStorage is persisted
      await new Promise(resolve => setTimeout(resolve, 50));
      // Fetch user data
      const userData = await getCurrentUser();
      setUser(userData);
    } catch (error) {
      clearStoredToken();
      setUser(null);
      throw error;
    } finally {
      setIsLoading(false);
      setIsOAuthPending(false);
    }
  }, []);

  useEffect(() => {
    // Prevent double-initialization in strict mode
    if (initRef.current) return;
    initRef.current = true;

    // Check if we're in the middle of an OAuth callback
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      if (params.get('token')) {
        // OAuth callback will handle initialization
        setIsOAuthPending(true);
        return;
      }
    }

    refreshUser();
  }, [refreshUser]);

  const login = async (credentials: LoginCredentials) => {
    await apiLogin(credentials);
    await refreshUser();
    router.push('/inventory');
  };

  const register = async (data: RegisterData) => {
    try {
      await apiRegister(data);
      // After registration, automatically log in
      await apiLogin({ email: data.email, password: data.password });
      await refreshUser();
      router.push('/inventory');
    } catch (error) {
      // Re-throw with better error message
      const message = error instanceof Error ? error.message : 'Registration failed';
      throw new Error(message);
    }
  };

  const logout = async () => {
    try {
      await apiLogout();
    } finally {
      setUser(null);
      router.push('/login');
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        isOAuthPending,
        login,
        register,
        logout,
        refreshUser,
        handleOAuthToken,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

// Hook for protecting routes
export function useRequireAuth(redirectTo: string = '/login') {
  const { isAuthenticated, isLoading, isOAuthPending } = useAuth();
  const router = useRouter();

  useEffect(() => {
    // Don't redirect during OAuth processing
    if (isOAuthPending) return;

    if (!isLoading && !isAuthenticated) {
      router.push(redirectTo);
    }
  }, [isAuthenticated, isLoading, isOAuthPending, router, redirectTo]);

  return { isLoading: isLoading || isOAuthPending, isAuthenticated };
}


