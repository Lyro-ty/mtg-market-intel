'use client';

import { useState, useEffect, type FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { LogIn, Mail, Lock, Sparkles, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { useAuth } from '@/contexts/AuthContext';
import { GoogleLoginButton } from '@/components/auth/GoogleLoginButton';
import { setStoredToken } from '@/lib/api';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { login, isAuthenticated, refreshUser } = useAuth();
  const router = useRouter();

  // Handle OAuth callback token
  useEffect(() => {
    const handleOAuthCallback = async () => {
      const params = new URLSearchParams(window.location.search);
      const token = params.get('token');
      const error = params.get('error');

      if (error) {
        setError('Google login failed. Please try again.');
        // Clean URL to remove error parameter
        window.history.replaceState({}, '', '/login');
        return;
      }

      if (token) {
        // Store token using the correct key
        setStoredToken(token);
        // Clean URL to remove sensitive token
        window.history.replaceState({}, '', '/login');
        // Sync auth state
        await refreshUser();
        // Redirect to inventory (consistent with normal login)
        router.push('/inventory');
      }
    };

    handleOAuthCallback();
  }, [router, refreshUser]);

  // Redirect if already authenticated
  if (isAuthenticated) {
    router.push('/inventory');
    return null;
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      await login({ email, password });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Invalid email or password');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex-1 flex items-center justify-center p-4 relative">
      {/* Background decoration */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-[rgb(var(--magic-purple))]/10 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-[rgb(var(--magic-green))]/10 rounded-full blur-3xl" />
      </div>

      <Card className="w-full max-w-md relative bg-card/80 backdrop-blur-xl border-border">
        <CardContent className="p-8">
          {/* Logo */}
          <div className="flex flex-col items-center mb-8">
            <div className="p-3 rounded-2xl gradient-arcane mb-4">
              <Sparkles className="w-8 h-8 text-white" />
            </div>
            <h1 className="text-2xl font-heading font-bold text-foreground">Dualcaster Deals</h1>
            <p className="text-muted-foreground mt-1">Sign in to your account</p>
          </div>

          {/* Error message */}
          {error && (
            <div className="mb-6 p-4 rounded-lg bg-destructive/10 border border-destructive/20 flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-destructive shrink-0" />
              <p className="text-destructive text-sm">{error}</p>
            </div>
          )}

          {/* Login form */}
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <label htmlFor="email" className="block text-sm font-medium text-foreground">
                Email
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="pl-11"
                  required
                />
              </div>
            </div>

            <div className="space-y-2">
              <label htmlFor="password" className="block text-sm font-medium text-foreground">
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="pl-11"
                  required
                />
              </div>
            </div>

            <Button
              type="submit"
              size="lg"
              className="w-full gradient-arcane hover:opacity-90 transition-opacity"
              disabled={isLoading}
            >
              {isLoading ? (
                <span className="flex items-center gap-2">
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Signing in...
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <LogIn className="w-4 h-4" />
                  Sign in
                </span>
              )}
            </Button>
          </form>

          {/* OAuth Divider */}
          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-border" />
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-2 bg-card text-muted-foreground">Or continue with</span>
            </div>
          </div>

          {/* Google Login */}
          <GoogleLoginButton disabled={isLoading} />

          {/* Register link */}
          <p className="mt-6 text-center text-sm text-muted-foreground">
            Don&apos;t have an account?{' '}
            <Link
              href="/register"
              className="text-[rgb(var(--accent))] hover:text-[rgb(var(--accent))]/80 font-medium transition-colors"
            >
              Create one
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}




