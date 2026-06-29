// API client for the Habit Tracker backend

import type {
  DashboardData,
  FoodEntry,
  FoodAnalysis,
  DailySummary,
  WeeklySummary,
  UserProfile,
  OnboardingData,
  WorkoutEntry,
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

export interface AdminOperations {
  access: {
    active: number;
    expired_unprocessed: number;
    expiring: {
      within_1_days: number;
      within_2_days: number;
      within_3_days: number;
    };
    open_events: number;
  };
  payments: {
    succeeded_today: number;
    revenue_today: number;
    pending_total: number;
    pending_old: number;
    recent_succeeded: Array<{
      payment_id: string;
      user_id: number;
      amount: number;
      created_at: number;
    }>;
    old_pending: Array<{
      payment_id: string;
      user_id: number;
      amount: number;
      status: string;
      created_at: number;
    }>;
  };
  cancellations: {
    today: number;
    reasons: Record<string, number>;
    recent: Array<{
      user_id: number;
      username: string;
      full_name: string;
      reason: string;
      created_at: number;
    }>;
  };
  retention: {
    auto_renewal_enabled: number;
    saved_payment_methods: number;
    auto_renewal_disabled_with_card: number;
    auto_renewal_failures: number;
    renewal_disabled_total: number;
    cards_unlinked_total: number;
    immediate_cancel_total: number;
  };
  events: Array<{
    id: number;
    event_type: string;
    severity: string;
    user_id?: number;
    payment_id?: string;
    message: string;
    created_at: number;
  }>;
}

export interface AdminConsoleSummary {
  total_users: number;
  active_users: number;
  expiring_3d: number;
  expired_users: number;
  never_paid: number;
  pending_payments: number;
  old_pending: number;
  open_events: number;
  critical_events: number;
  auto_renewal_enabled: number;
  saved_cards: number;
  renewal_failures: number;
}

export interface AdminUserListItem {
  user_id: number;
  username: string;
  full_name: string;
  phone: string;
  expires_at: number;
  status: 'active' | 'expiring' | 'expired' | 'no_access';
  days_left: number;
  auto_renewal: boolean;
  has_payment_method: boolean;
  auto_renewal_failures: number;
  auto_renewal_agreed_at?: number | null;
  payments_count: number;
  paid_total: number;
  last_payment_status: string;
  last_payment_at?: number | null;
  last_cancel_reason: string;
  last_cancel_at?: number | null;
  open_events: number;
}

export interface AdminPaymentItem {
  payment_id: string;
  user_id: number;
  amount: number;
  status: string;
  created_at: number;
  username: string;
  full_name: string;
  user_status: string;
}

export interface AdminEventItem {
  id: number;
  event_type: string;
  severity: string;
  user_id?: number;
  payment_id?: string;
  message: string;
  resolved: boolean;
  created_at: number;
  username: string;
  full_name: string;
}

export interface AdminUserDetail {
  user: AdminUserListItem & {
    payment_method_id: string;
    auto_renewal_agreed_at?: number | null;
    referral_code: string;
  };
  profile: UserProfile | null;
  payments: Array<{
    payment_id: string;
    amount: number;
    status: string;
    created_at: number;
  }>;
  cancellations: Array<{
    reason: string;
    created_at: number;
  }>;
  events: Array<{
    id: number;
    event_type: string;
    severity: string;
    payment_id?: string;
    message: string;
    resolved: boolean;
    created_at: number;
  }>;
  activity: {
    food_entries: number;
    sleep_entries: number;
    workout_entries: number;
    last_food_at?: number | null;
    last_workout_at?: number | null;
  };
}

export interface Paginated<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
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
    fullnessAfter?: number,
    ateWithoutGadgets?: boolean
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
          ate_without_gadgets: ateWithoutGadgets,
        }),
      }
    ),

  addFoodPhoto: (
    photo: File,
    time?: string,
    hungerBefore?: number,
    fullnessAfter?: number,
    context?: string,
    ateWithoutGadgets?: boolean
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
    if (ateWithoutGadgets !== undefined) {
      formData.append('ate_without_gadgets', ateWithoutGadgets.toString());
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

  // Workout Tracker
  addWorkout: (workoutName: string, durationMinutes: number, intensity: number, date?: string) =>
    apiFetch<{ success: boolean; workout_id: number }>('/workouts', {
      method: 'POST',
      body: JSON.stringify({
        workout_name: workoutName,
        duration_minutes: durationMinutes,
        intensity,
        date,
      }),
    }),

  getWorkoutsByDate: (date: string) =>
    apiFetch<{ date: string; workouts: WorkoutEntry[] }>(`/workouts/${date}`),

  deleteWorkout: (workoutId: number) =>
    apiFetch<{ success: boolean }>(`/workouts/${workoutId}`, {
      method: 'DELETE',
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

  // Payment
  createPayment: () =>
    apiFetch<{ payment_id: string; confirmation_url: string; amount: number }>(
      '/payment/create',
      { method: 'POST' }
    ),

  checkPayment: () =>
    apiFetch<{
      status: string;
      payment_id?: string;
      subscription_active: boolean;
      expires_at?: number;
      invite_link?: string;
      message?: string;
    }>('/payment/check', { method: 'POST' }),

  // Auto-renewal
  getAutoRenewalStatus: () =>
    apiFetch<{ enabled: boolean; has_payment_method: boolean; failures: number }>('/autorenewal'),

  toggleAutoRenewal: () =>
    apiFetch<{ enabled: boolean }>('/autorenewal/toggle', { method: 'POST' }),

  unlinkPaymentMethod: () =>
    apiFetch<{ ok: boolean; enabled: boolean; has_payment_method: boolean }>(
      '/autorenewal/unlink',
      { method: 'POST' }
    ),

  // Referral
  getReferralInfo: () =>
    apiFetch<{
      code: string;
      link: string;
      stats: { total_invited: number; total_paid: number; available_rewards: number };
    }>('/referral'),

  // Gamification
  getStreak: () =>
    apiFetch<{ current: number; best: number }>('/streak'),

  getAchievements: () =>
    apiFetch<{
      achievements: Array<{
        id: string;
        name: string;
        description: string;
        icon: string;
        unlocked: boolean;
        unlocked_at?: string;
      }>;
    }>('/achievements'),

  // Admin
  adminMe: () =>
    apiFetch<{ admin: boolean; user: { user_id: number; username?: string; first_name?: string } }>('/admin/me'),

  getAdminStats: () =>
    apiFetch<Record<string, unknown>>('/admin/stats'),

  getAdminOperations: () =>
    apiFetch<AdminOperations>('/admin/operations'),

  getAdminConsoleSummary: () =>
    apiFetch<AdminConsoleSummary>('/admin/console/summary'),

  getAdminUsers: (params: { status?: string; q?: string; limit?: number; offset?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.status) query.set('status', params.status);
    if (params.q) query.set('q', params.q);
    if (params.limit) query.set('limit', String(params.limit));
    if (params.offset) query.set('offset', String(params.offset));
    const suffix = query.toString() ? `?${query.toString()}` : '';
    return apiFetch<Paginated<AdminUserListItem>>(`/admin/users${suffix}`);
  },

  getAdminUserDetail: (userId: number) =>
    apiFetch<AdminUserDetail>(`/admin/users/${userId}`),

  extendAdminUserSubscription: (userId: number, days: number) =>
    apiFetch<{ ok: boolean; expires_at: number }>(`/admin/users/${userId}/extend`, {
      method: 'POST',
      body: JSON.stringify({ days }),
    }),

  revokeAdminUserSubscription: (userId: number, reason = 'admin_revoke_web') =>
    apiFetch<{ ok: boolean; expires_at: number; removed_from_group: boolean }>(`/admin/users/${userId}/revoke`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),

  sendAdminInvite: (userId: number) =>
    apiFetch<{ ok: boolean; invite_link: string; sent: boolean }>(`/admin/users/${userId}/send-invite`, {
      method: 'POST',
    }),

  updateAdminUserAutoRenewal: (userId: number, enabled: boolean) =>
    apiFetch<{ ok: boolean; enabled: boolean }>(`/admin/users/${userId}/autorenewal`, {
      method: 'POST',
      body: JSON.stringify({ enabled }),
    }),

  unlinkAdminUserCard: (userId: number) =>
    apiFetch<{ ok: boolean }>(`/admin/users/${userId}/unlink-card`, {
      method: 'POST',
    }),

  getAdminPayments: (params: { status?: string; q?: string; limit?: number; offset?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.status) query.set('status', params.status);
    if (params.q) query.set('q', params.q);
    if (params.limit) query.set('limit', String(params.limit));
    if (params.offset) query.set('offset', String(params.offset));
    const suffix = query.toString() ? `?${query.toString()}` : '';
    return apiFetch<Paginated<AdminPaymentItem>>(`/admin/payments${suffix}`);
  },

  getAdminEvents: (params: { state?: string; severity?: string; limit?: number; offset?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.state) query.set('state', params.state);
    if (params.severity) query.set('severity', params.severity);
    if (params.limit) query.set('limit', String(params.limit));
    if (params.offset) query.set('offset', String(params.offset));
    const suffix = query.toString() ? `?${query.toString()}` : '';
    return apiFetch<Paginated<AdminEventItem>>(`/admin/events${suffix}`);
  },

  resolveAdminEvent: (eventId: number) =>
    apiFetch<{ ok: boolean }>(`/admin/events/${eventId}/resolve`, {
      method: 'POST',
    }),

  // Feedback
  sendFeedback: (message: string) =>
    apiFetch<{ ok: boolean }>('/feedback', {
      method: 'POST',
      body: JSON.stringify({ message }),
    }),
};

export default api;
