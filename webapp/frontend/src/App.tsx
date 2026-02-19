// Main App component with routing

import { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useStore } from './store/useStore';
import { useTelegram } from './hooks/useTelegram';
import { useTheme } from './hooks/useTheme';
import { api, SubscriptionRequiredError } from './api/client';
import { LoadingSpinner } from './components/Layout';

// Pages
import { Dashboard } from './pages/Dashboard';
import { Onboarding } from './pages/Onboarding';
import { AddFood } from './pages/AddFood';
import { AddWorkout } from './pages/AddWorkout';
import { FoodList } from './pages/FoodList';
import { FoodEntryDetail } from './pages/FoodEntryDetail';
import { Sleep } from './pages/Sleep';
import { DailySummary } from './pages/DailySummary';
import { WeeklySummary } from './pages/WeeklySummary';
import { Settings } from './pages/Settings';
import { EditRequest } from './pages/EditRequest';
import { SubscriptionOnboarding } from './pages/SubscriptionOnboarding';
import { FoodCalendar } from './pages/FoodCalendar';
import { Achievements } from './pages/Achievements';
import { AdminDashboard } from './pages/AdminDashboard';

import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30000,
    },
  },
});

// Auth wrapper component
function AuthenticatedApp() {
  const {
    isAuthenticated,
    setAuthenticated,
    subscriptionActive,
    setSubscriptionActive,
    profile,
    setProfile,
    setUser,
    setLoading,
    isLoading,
  } = useStore();
  const { isAvailable } = useTelegram();
  const [authError, setAuthError] = useState<string | null>(null);

  // Initialize theme
  useTheme();

  useEffect(() => {
    initializeApp();
  }, []);

  const initializeApp = async () => {
    setLoading(true);
    setAuthError(null);

    // Debug: log Telegram WebApp info
    console.log('Telegram WebApp available:', isAvailable);
    console.log('window.Telegram:', window.Telegram);
    console.log('WebApp object:', window.Telegram?.WebApp);
    console.log('initData:', window.Telegram?.WebApp?.initData);
    console.log('initDataUnsafe:', window.Telegram?.WebApp?.initDataUnsafe);

    try {
      // Check subscription and get user data
      const response = await api.me();

      setAuthenticated(true);
      setSubscriptionActive(true);
      setUser({
        user_id: response.user.user_id,
        username: response.user.username,
        first_name: response.user.first_name,
      });

      if (response.profile) {
        setProfile(response.profile);
      }
    } catch (error) {
      if (error instanceof SubscriptionRequiredError) {
        setSubscriptionActive(false);
        setAuthenticated(true);
      } else {
        console.error('Auth error:', error);

        // Если есть Telegram данные, но авторизация не прошла - показываем онбординг
        // (скорее всего проблема с подпиской, а не с auth)
        if (isAvailable && window.Telegram?.WebApp?.initData) {
          setSubscriptionActive(false);
          setAuthenticated(true);
        } else if (import.meta.env.DEV && !isAvailable) {
          // In development, allow access without Telegram
          setAuthenticated(true);
          setSubscriptionActive(true);
        } else {
          setAuthError('Не удалось авторизоваться');
        }
      }
    } finally {
      setLoading(false);
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <LoadingSpinner size="lg" />
          <p className="mt-4 text-sm" style={{ color: 'var(--text-secondary)' }}>
            Загрузка...
          </p>
        </div>
      </div>
    );
  }

  // Auth error
  if (authError) {
    const tg = window.Telegram?.WebApp;
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="text-center">
          <div
            className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4"
            style={{ background: 'var(--error-soft)' }}
          >
            <span className="text-2xl">⚠️</span>
          </div>
          <h1 className="text-xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>
            Ошибка
          </h1>
          <p className="text-sm mb-4" style={{ color: 'var(--text-secondary)' }}>
            {authError}
          </p>
          {/* Debug info */}
          <div className="text-xs text-left mb-4 p-2 rounded" style={{ background: 'var(--bg-secondary)', color: 'var(--text-secondary)' }}>
            <p>TG available: {tg ? 'Yes' : 'No'}</p>
            <p>initData: {tg?.initData ? `${tg.initData.substring(0, 30)}...` : 'EMPTY'}</p>
            <p>User: {tg?.initDataUnsafe?.user ? JSON.stringify(tg.initDataUnsafe.user) : 'null'}</p>
            <p>Platform: {(tg as any)?.platform || 'unknown'}</p>
          </div>
          <button
            onClick={initializeApp}
            className="btn-primary"
          >
            Попробовать снова
          </button>
        </div>
      </div>
    );
  }

  // No subscription - показываем онбординг
  if (isAuthenticated && !subscriptionActive) {
    return <SubscriptionOnboarding />;
  }

  // Check if needs onboarding
  const needsOnboarding = !profile?.onboarding_completed;

  return (
    <Routes>
      {/* Onboarding */}
      <Route
        path="/onboarding"
        element={<Onboarding />}
      />

      {/* Protected routes */}
      <Route
        path="/"
        element={
          needsOnboarding ? <Navigate to="/onboarding" replace /> : <Dashboard />
        }
      />
      <Route
        path="/food/add"
        element={
          needsOnboarding ? <Navigate to="/onboarding" replace /> : <AddFood />
        }
      />
      <Route
        path="/food/:id"
        element={
          needsOnboarding ? <Navigate to="/onboarding" replace /> : <FoodEntryDetail />
        }
      />
      <Route
        path="/food"
        element={
          needsOnboarding ? <Navigate to="/onboarding" replace /> : <FoodList />
        }
      />
      <Route
        path="/workout/add"
        element={
          needsOnboarding ? <Navigate to="/onboarding" replace /> : <AddWorkout />
        }
      />
      <Route
        path="/sleep"
        element={
          needsOnboarding ? <Navigate to="/onboarding" replace /> : <Sleep />
        }
      />
      <Route
        path="/summary"
        element={
          needsOnboarding ? <Navigate to="/onboarding" replace /> : <DailySummary />
        }
      />
      <Route
        path="/weekly"
        element={
          needsOnboarding ? <Navigate to="/onboarding" replace /> : <WeeklySummary />
        }
      />
      <Route
        path="/settings"
        element={
          needsOnboarding ? <Navigate to="/onboarding" replace /> : <Settings />
        }
      />
      <Route
        path="/edit-request"
        element={
          needsOnboarding ? <Navigate to="/onboarding" replace /> : <EditRequest />
        }
      />
      <Route
        path="/calendar"
        element={
          needsOnboarding ? <Navigate to="/onboarding" replace /> : <FoodCalendar />
        }
      />
      <Route
        path="/achievements"
        element={
          needsOnboarding ? <Navigate to="/onboarding" replace /> : <Achievements />
        }
      />
      <Route
        path="/admin"
        element={<AdminDashboard />}
      />

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthenticatedApp />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
