// Global state store using Zustand

import { create } from 'zustand';
import type { UserProfile, TelegramUser, DashboardData, Goal, TrainingType, ActivityLevel } from '../types';

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

  // Onboarding
  onboardingStep: number;
  onboardingData: {
    goal: Goal | null;
    training_type: TrainingType | null;
    activity_level: ActivityLevel | null;
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
  food_tracker_enabled: false,
  sleep_tracker_enabled: false,
  weekly_review_enabled: false,
  evening_summary_time: '21:00',
  morning_question_time: '08:00',
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
