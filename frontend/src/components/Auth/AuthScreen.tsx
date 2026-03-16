import { useState } from 'react';
import { useAuthStore } from '@/stores/authStore';
import { api } from '@/services/api';
import { LogIn, UserPlus, Eye, EyeOff } from 'lucide-react';

type Mode = 'login' | 'signup';

export function AuthScreen() {
  const [mode, setMode] = useState<Mode>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const login = useAuthStore((s) => s.login);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!email || !password) {
      setError('Email and password are required.');
      return;
    }

    if (mode === 'signup' && password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    if (mode === 'signup' && password.length < 6) {
      setError('Password must be at least 6 characters.');
      return;
    }

    setLoading(true);
    try {
      const result =
        mode === 'signup'
          ? await api.signup(email, password)
          : await api.login(email, password);

      login(result.token, {
        user_id: result.user_id,
        email: result.email,
        display_name: result.display_name,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.');
    } finally {
      setLoading(false);
    }
  };

  const switchMode = () => {
    setMode(mode === 'login' ? 'signup' : 'login');
    setError('');
    setConfirmPassword('');
  };

  const inputClass =
    'w-full px-4 py-3 rounded-lg bg-gray-100 dark:bg-white/5 border border-gray-200 dark:border-white/10 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-white/30 focus:outline-none focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/30 transition-colors';

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950 px-4">
      <div className="w-full max-w-md">
        {/* Logo / Title */}
        <div className="text-center mb-8">
          <div className="flex justify-center mb-3">
            <img
              src="/assets/logodark.png"
              alt="ArchFlow"
              className="h-16 w-auto dark:hidden"
            />
            <img
              src="/assets/logolight.png"
              alt="ArchFlow"
              className="h-16 w-auto hidden dark:block"
            />
          </div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
            ArchFlow
          </h1>
          <p className="mt-2 text-sm text-gray-500 dark:text-white/40">
            AI-powered architecture diagram designer
          </p>
        </div>

        {/* Card */}
        <div className="glass-dark rounded-2xl p-8 border border-gray-200 dark:border-white/5">
          {/* Tab toggle */}
          <div className="flex mb-6 bg-gray-100 dark:bg-white/5 rounded-lg p-1">
            <button
              onClick={() => { setMode('login'); setError(''); setConfirmPassword(''); }}
              className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${mode === 'login'
                ? 'bg-primary-500/20 text-primary-600 dark:text-primary-400'
                : 'text-gray-400 dark:text-white/40 hover:text-gray-600 dark:hover:text-white/60'
                }`}
            >
              Log In
            </button>
            <button
              onClick={() => { setMode('signup'); setError(''); }}
              className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${mode === 'signup'
                ? 'bg-primary-500/20 text-primary-600 dark:text-primary-400'
                : 'text-gray-400 dark:text-white/40 hover:text-gray-600 dark:hover:text-white/60'
                }`}
            >
              Sign Up
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-white/50 mb-1.5">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className={inputClass}
                autoComplete="email"
                autoFocus
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-white/50 mb-1.5">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  className={inputClass}
                  autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-white/30 hover:text-gray-600 dark:hover:text-white/60 transition-colors"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {mode === 'signup' && (
              <div>
                <label className="block text-xs font-medium text-gray-500 dark:text-white/50 mb-1.5">
                  Confirm Password
                </label>
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Confirm your password"
                  className={inputClass}
                  autoComplete="new-password"
                />
              </div>
            )}

            {error && (
              <div className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 rounded-lg px-3 py-2">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 py-3 rounded-lg bg-primary-500 hover:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium transition-colors"
            >
              {loading ? (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : mode === 'login' ? (
                <LogIn className="w-4 h-4" />
              ) : (
                <UserPlus className="w-4 h-4" />
              )}
              {loading ? 'Please wait...' : mode === 'login' ? 'Log In' : 'Create Account'}
            </button>
          </form>

          <p className="mt-4 text-center text-xs text-gray-400 dark:text-white/30">
            {mode === 'login' ? "Don't have an account? " : 'Already have an account? '}
            <button
              onClick={switchMode}
              className="text-primary-500 dark:text-primary-400 hover:text-primary-600 dark:hover:text-primary-300 transition-colors"
            >
              {mode === 'login' ? 'Sign up' : 'Log in'}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}
