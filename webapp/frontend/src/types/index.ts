// Types for the Habit Tracker WebApp

export type Goal = 'maintain' | 'lose' | 'gain';
export type TrainingType = 'marathon' | 'own' | 'mixed';
export type ActivityLevel = 'active' | 'medium' | 'calm';

// Theme types
export type ThemeMode = 'light' | 'dark' | 'system';
export type ColorScheme = 'peach' | 'neutral' | 'lavender';

export interface UserProfile {
  user_id: number;
  goal: Goal | null;
  training_type: TrainingType | null;
  activity_level: ActivityLevel | null;
  food_tracker_enabled: boolean;
  sleep_tracker_enabled: boolean;
  weekly_review_enabled: boolean;
  evening_summary_time: string;
  morning_question_time: string;
  timezone_offset?: number;
  onboarding_completed: boolean;
  created_at?: number;
  updated_at?: number;
}

export interface TelegramUser {
  user_id: number;
  username?: string;
  first_name?: string;
  last_name?: string;
  language_code?: string;
}

export interface FoodCategories {
  proteins_animal: string[];
  proteins_plant: string[];
  fats: string[];
  carbs_slow: string[];
  carbs_fast: string[];
  vegetables: string[];
}

export interface FoodEntry {
  id: number;
  time: string;
  description: string;
  photo_file_id?: string;
  categories?: FoodCategories;
  raw_input?: string;
  source: 'webapp' | 'telegram';
  hunger_before?: number;  // 1-5
  fullness_after?: number;  // 1-5
}

export interface FoodAnalysis {
  description: string;
  products: string[];
  categories: FoodCategories;
  error?: string;
}

export interface DailySummary {
  foods_list: string[];
  analysis: string;
  balance_note: string;
  suggestion?: string | null;
  error?: string;
}

export interface WeeklySummary {
  food_diversity_by_day: Record<string, 'высокое' | 'среднее' | 'низкое'>;
  sleep_average: number | null;
  patterns: string[];
  food_sleep_connection?: string | null;
  error?: string;
}

export interface DashboardData {
  date: string;
  profile: UserProfile | null;
  food: {
    entries: FoodEntry[];
    count: number;
  };
  sleep: {
    score: number | null;
  };
  summary: {
    available: boolean;
    data: DailySummary | null;
  };
}

export interface OnboardingData {
  goal: Goal;
  training_type: TrainingType;
  activity_level: ActivityLevel;
  food_tracker_enabled: boolean;
  sleep_tracker_enabled: boolean;
  weekly_review_enabled: boolean;
  evening_summary_time: string;
  morning_question_time: string;
  timezone_offset?: number;
}

// Telegram WebApp types
declare global {
  interface Window {
    Telegram?: {
      WebApp: TelegramWebApp;
    };
  }
}

export interface TelegramWebApp {
  initData: string;
  initDataUnsafe: {
    user?: {
      id: number;
      first_name: string;
      last_name?: string;
      username?: string;
      language_code?: string;
    };
    auth_date: number;
    hash: string;
  };
  colorScheme: 'light' | 'dark';
  themeParams: {
    bg_color?: string;
    text_color?: string;
    hint_color?: string;
    link_color?: string;
    button_color?: string;
    button_text_color?: string;
    secondary_bg_color?: string;
  };
  isExpanded: boolean;
  viewportHeight: number;
  viewportStableHeight: number;
  MainButton: {
    text: string;
    color: string;
    textColor: string;
    isVisible: boolean;
    isActive: boolean;
    isProgressVisible: boolean;
    setText: (text: string) => void;
    onClick: (callback: () => void) => void;
    offClick: (callback: () => void) => void;
    show: () => void;
    hide: () => void;
    enable: () => void;
    disable: () => void;
    showProgress: (leaveActive?: boolean) => void;
    hideProgress: () => void;
  };
  BackButton: {
    isVisible: boolean;
    onClick: (callback: () => void) => void;
    offClick: (callback: () => void) => void;
    show: () => void;
    hide: () => void;
  };
  HapticFeedback: {
    impactOccurred: (style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft') => void;
    notificationOccurred: (type: 'error' | 'success' | 'warning') => void;
    selectionChanged: () => void;
  };
  close: () => void;
  expand: () => void;
  ready: () => void;
  setHeaderColor: (color: string) => void;
  setBackgroundColor: (color: string) => void;
  enableClosingConfirmation: () => void;
  disableClosingConfirmation: () => void;
  onEvent: (eventType: string, callback: () => void) => void;
  offEvent: (eventType: string, callback: () => void) => void;
  sendData: (data: string) => void;
  openLink: (url: string, options?: { try_instant_view?: boolean }) => void;
  openTelegramLink: (url: string) => void;
  showPopup: (params: {
    title?: string;
    message: string;
    buttons?: Array<{
      id?: string;
      type?: 'default' | 'ok' | 'close' | 'cancel' | 'destructive';
      text?: string;
    }>;
  }, callback?: (button_id: string) => void) => void;
  showAlert: (message: string, callback?: () => void) => void;
  showConfirm: (message: string, callback?: (confirmed: boolean) => void) => void;
}
