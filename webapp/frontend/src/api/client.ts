// API client for the Habit Tracker backend

import type {
  DashboardData,
  FoodEntry,
  FoodAnalysis,
  DailySummary,
  WeeklySummary,
  UserProfile,
  OnboardingData,
} from '../types';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

// Get Telegram initData for authentication
function getInitData(): string {
  if (window.Telegram?.WebApp?.initData) {
    return window.Telegram.WebApp.initData;
  }
  // For development
  return '';
}

// Base fetch with auth headers
async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const initData = getInitData();

  const headers: Record<string, string> = {};

  // Copy existing headers
  if (options.headers) {
    const existingHeaders = options.headers as Record<string, string>;
    Object.keys(existingHeaders).forEach(key => {
      headers[key] = existingHeaders[key];
    });
  }

  if (initData) {
    headers['X-Telegram-Init-Data'] = initData;
  }

  // Don't set Content-Type for FormData
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  // Handle subscription required
  if (response.status === 403) {
    const subscriptionStatus = response.headers.get('X-Subscription-Status');
    if (subscriptionStatus === 'inactive') {
      throw new SubscriptionRequiredError('Subscription required');
    }
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new ApiError(error.detail || 'Request failed', response.status);
  }

  return response.json();
}

// Custom error classes
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export class SubscriptionRequiredError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'SubscriptionRequiredError';
  }
}

// API methods
export const api = {
  // Health check
  health: () => apiFetch<{ status: string; timestamp: string }>('/health'),

  // Auth & Profile
  me: () => apiFetch<{
    user: { user_id: number; username?: string; first_name?: string };
    profile: UserProfile | null;
    subscription_active: boolean;
  }>('/me'),

  subscriptionStatus: () => apiFetch<{
    active: boolean;
    user_id?: number;
    reason?: string;
  }>('/subscription-status'),

  // Onboarding
  getOnboarding: () => apiFetch<UserProfile | Record<string, never>>('/onboarding'),

  saveOnboarding: (data: OnboardingData) =>
    apiFetch<{ success: boolean }>('/onboarding', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateSettings: (data: Partial<OnboardingData>) =>
    apiFetch<{ success: boolean }>('/settings', {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  // Food Tracker
  getTodayFood: () =>
    apiFetch<{ date: string; entries: FoodEntry[] }>('/food/today'),

  getFoodByDate: (date: string) =>
    apiFetch<{ date: string; entries: FoodEntry[] }>(`/food/${date}`),

  addFoodText: (
    text: string,
    time?: string,
    hungerBefore?: number,
    fullnessAfter?: number
  ) =>
    apiFetch<{ success: boolean; entry_id: number; analysis: FoodAnalysis }>(
      '/food/text',
      {
        method: 'POST',
        body: JSON.stringify({
          text,
          time,
          hunger_before: hungerBefore,
          fullness_after: fullnessAfter,
        }),
      }
    ),

  addFoodPhoto: (
    photo: File,
    time?: string,
    hungerBefore?: number,
    fullnessAfter?: number,
    context?: string
  ) => {
    const formData = new FormData();
    formData.append('photo', photo);
    if (time) {
      formData.append('time', time);
    }
    if (hungerBefore !== undefined) {
      formData.append('hunger_before', hungerBefore.toString());
    }
    if (fullnessAfter !== undefined) {
      formData.append('fullness_after', fullnessAfter.toString());
    }
    if (context) {
      formData.append('context', context);
    }
    return apiFetch<{ success: boolean; entry_id: number; analysis: FoodAnalysis }>(
      '/food/photo',
      {
        method: 'POST',
        body: formData,
      }
    );
  },

  updateFoodEntryFeelings: (
    entryId: number,
    hungerBefore?: number,
    fullnessAfter?: number
  ) =>
    apiFetch<{ success: boolean }>(`/food/${entryId}/feelings`, {
      method: 'PATCH',
      body: JSON.stringify({
        hunger_before: hungerBefore,
        fullness_after: fullnessAfter,
      }),
    }),

  updateFoodEntry: (entryId: number, description: string) =>
    apiFetch<{ success: boolean }>(`/food/${entryId}`, {
      method: 'PATCH',
      body: JSON.stringify({
        description,
      }),
    }),

  deleteFoodEntry: (entryId: number) =>
    apiFetch<{ success: boolean }>(`/food/${entryId}`, {
      method: 'DELETE',
    }),

  getFoodCalendar: (year: number, month: number) =>
    apiFetch<{
      year: number;
      month: number;
      days: Record<string, { count: number; entries: FoodEntry[] }>;
    }>(`/food/calendar/${year}/${month}`),

  // Sleep Tracker
  getTodaySleep: () =>
    apiFetch<{ date: string; score: number | null }>('/sleep/today'),

  addSleepEntry: (score: number, date?: string) =>
    apiFetch<{ success: boolean }>('/sleep', {
      method: 'POST',
      body: JSON.stringify({ score, date }),
    }),

  // Daily Summary
  getTodaySummary: () =>
    apiFetch<{
      date: string;
      summary: DailySummary | null;
      cached?: boolean;
      message?: string;
    }>('/summary/today'),

  getSummaryByDate: (date: string) =>
    apiFetch<{ date: string; summary: DailySummary | null }>(`/summary/${date}`),

  recalculateSummary: () =>
    apiFetch<{ date: string; summary: DailySummary | null; recalculated?: boolean }>(
      '/summary/recalculate',
      { method: 'POST' }
    ),

  // Weekly Summary
  getCurrentWeekly: () =>
    apiFetch<{
      week_start: string;
      summary: WeeklySummary | null;
      cached?: boolean;
      message?: string;
    }>('/weekly/current'),

  getWeeklyByDate: (weekStart: string) =>
    apiFetch<{ week_start: string; summary: WeeklySummary | null }>(
      `/weekly/${weekStart}`
    ),

  // Dashboard
  getDashboard: () => apiFetch<DashboardData>('/dashboard'),
};

export default api;
