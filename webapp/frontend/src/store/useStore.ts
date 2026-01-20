// Global state store using Zustand

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { UserProfile, TelegramUser, DashboardData, Goal, TrainingType, ActivityLevel, Gender, ThemeMode, ColorScheme } from '../types';

// Helper to get system theme
const getSystemTheme = (): 'light' | 'dark' => {
  if (typeof window !== 'undefined' && window.matchMedia) {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  return 'light';
};

interface AppState {
  // User & Auth
  user: TelegramUser | null;
  profile: UserProfile | null;
  isAuthenticated: boolean;
  subscriptionActive: boolean;

  // UI State
  isDarkMode: boolean;
  isLoading: boolean;
  error: string | null;

  // Theme
  themeMode: ThemeMode;
  colorScheme: ColorScheme;

  // Onboarding
  onboardingStep: number;
  onboardingData: {
    goal: Goal | null;
    training_type: TrainingType | null;
    activity_level: ActivityLevel | null;
    gender: Gender | null;
    food_tracker_enabled: boolean;
    sleep_tracker_enabled: boolean;
    weekly_review_enabled: boolean;
    evening_summary_time: string;
    morning_question_time: string;
  };

  // Dashboard cache
  dashboard: DashboardData | null;

  // Actions
  setUser: (user: TelegramUser | null) => void;
  setProfile: (profile: UserProfile | null) => void;
  setAuthenticated: (isAuthenticated: boolean) => void;
  setSubscriptionActive: (active: boolean) => void;
  setDarkMode: (isDark: boolean) => void;
  setLoading: (isLoading: boolean) => void;
  setError: (error: string | null) => void;
  setThemeMode: (mode: ThemeMode) => void;
  setColorScheme: (scheme: ColorScheme) => void;
  setOnboardingStep: (step: number) => void;
  updateOnboardingData: (data: Partial<AppState['onboardingData']>) => void;
  resetOnboardingData: () => void;
  setDashboard: (data: DashboardData | null) => void;
  reset: () => void;
}

const initialOnboardingData = {
  goal: null,
  training_type: null,
  activity_level: null,
  gender: null,
  food_tracker_enabled: false,
  sleep_tracker_enabled: false,
  weekly_review_enabled: false,
  evening_summary_time: '21:00',
  morning_question_time: '08:00',
};

// Theme settings store (persisted)
interface ThemeState {
  themeMode: ThemeMode;
  colorScheme: ColorScheme;
  setThemeMode: (mode: ThemeMode) => void;
  setColorScheme: (scheme: ColorScheme) => void;
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      themeMode: 'system',
      colorScheme: 'peach',
      setThemeMode: (themeMode) => set({ themeMode }),
      setColorScheme: (colorScheme) => set({ colorScheme }),
    }),
    {
      name: 'yourbody-theme',
    }
  )
);

// Helper to get effective dark mode
export const getEffectiveDarkMode = (themeMode: ThemeMode): boolean => {
  if (themeMode === 'system') {
    return getSystemTheme() === 'dark';
  }
  return themeMode === 'dark';
};

export const useStore = create<AppState>((set) => ({
  // Initial state
  user: null,
  profile: null,
  isAuthenticated: false,
  subscriptionActive: false,
  isDarkMode: false,
  isLoading: true,
  error: null,
  themeMode: 'system',
  colorScheme: 'peach',
  onboardingStep: 0,
  onboardingData: { ...initialOnboardingData },
  dashboard: null,

  // Actions
  setUser: (user) => set({ user }),
  setProfile: (profile) => set({ profile }),
  setAuthenticated: (isAuthenticated) => set({ isAuthenticated }),
  setSubscriptionActive: (subscriptionActive) => set({ subscriptionActive }),
  setDarkMode: (isDarkMode) => set({ isDarkMode }),
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
  setThemeMode: (themeMode) => set({ themeMode }),
  setColorScheme: (colorScheme) => set({ colorScheme }),
  setOnboardingStep: (onboardingStep) => set({ onboardingStep }),
  updateOnboardingData: (data) =>
    set((state) => ({
      onboardingData: { ...state.onboardingData, ...data },
    })),
  resetOnboardingData: () => set({ onboardingData: { ...initialOnboardingData } }),
  setDashboard: (dashboard) => set({ dashboard }),
  reset: () =>
    set({
      user: null,
      profile: null,
      isAuthenticated: false,
      subscriptionActive: false,
      isLoading: false,
      error: null,
      onboardingStep: 0,
      onboardingData: { ...initialOnboardingData },
      dashboard: null,
    }),
}));

export default useStore;
