// Settings page - edit profile and preferences

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Layout, Card, Button } from '../components/Layout';
import { useStore } from '../store/useStore';
import { useTelegram } from '../hooks/useTelegram';
import { useTheme, themeOptions, colorSchemeOptions } from '../hooks/useTheme';
import { api } from '../api/client';
import type { Goal, TrainingType, ActivityLevel } from '../types';
import {
  ArrowLeft,
  Target,
  Dumbbell,
  Utensils,
  Moon,
  Calendar,
  Clock,
  Check,
  Palette,
  Sun
} from 'lucide-react';

export function Settings() {
  const navigate = useNavigate();
  const { haptic } = useTelegram();
  const { profile, setProfile } = useStore();
  const { themeMode, colorScheme, setThemeMode, setColorScheme } = useTheme();

  const [isSaving, setIsSaving] = useState(false);
  const [localSettings, setLocalSettings] = useState({
    goal: profile?.goal || 'maintain' as Goal,
    training_type: profile?.training_type || 'marathon' as TrainingType,
    activity_level: profile?.activity_level || 'medium' as ActivityLevel,
    food_tracker_enabled: profile?.food_tracker_enabled || false,
    sleep_tracker_enabled: profile?.sleep_tracker_enabled || false,
    weekly_review_enabled: profile?.weekly_review_enabled || false,
    evening_summary_time: profile?.evening_summary_time || '21:00',
    morning_question_time: profile?.morning_question_time || '08:00',
  });

  useEffect(() => {
    if (profile) {
      setLocalSettings({
        goal: profile.goal || 'maintain',
        training_type: profile.training_type || 'marathon',
        activity_level: profile.activity_level || 'medium',
        food_tracker_enabled: profile.food_tracker_enabled,
        sleep_tracker_enabled: profile.sleep_tracker_enabled,
        weekly_review_enabled: profile.weekly_review_enabled,
        evening_summary_time: profile.evening_summary_time,
        morning_question_time: profile.morning_question_time,
      });
    }
  }, [profile]);

  const handleSave = async () => {
    setIsSaving(true);
    haptic('medium');

    try {
      await api.updateSettings(localSettings);

      // Update local profile
      if (profile) {
        setProfile({
          ...profile,
          ...localSettings,
        });
      }

      haptic('success');
      navigate('/');
    } catch (err) {
      console.error('Failed to save settings:', err);
      haptic('error');
    } finally {
      setIsSaving(false);
    }
  };

  const goals: { value: Goal; label: string }[] = [
    { value: 'lose', label: 'Снижение' },
    { value: 'maintain', label: 'Поддержание' },
    { value: 'gain', label: 'Набор' },
  ];

  const trainingTypes: { value: TrainingType; label: string }[] = [
    { value: 'marathon', label: 'С Настей' },
    { value: 'own', label: 'Свои' },
    { value: 'mixed', label: 'Смешанный' },
  ];

  const activityLevels: { value: ActivityLevel; label: string }[] = [
    { value: 'active', label: 'Активный' },
    { value: 'medium', label: 'Средний' },
    { value: 'calm', label: 'Спокойный' },
  ];

  const timeOptions = {
    morning: ['06:00', '07:00', '08:00', '09:00', '10:00', '11:00'],
    evening: ['18:00', '19:00', '20:00', '21:00', '22:00', '23:00'],
  };

  return (
    <Layout>
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => navigate(-1)}
          className="p-2 rounded-xl transition-colors"
          style={{ background: 'var(--bg-glass)' }}
        >
          <ArrowLeft className="w-5 h-5" style={{ color: 'var(--text-primary)' }} />
        </button>
        <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
          Настройки
        </h1>
      </div>

      <div className="space-y-4">
        {/* Goal */}
        <Card>
          <div className="flex items-center gap-2 mb-3">
            <Target className="w-5 h-5" style={{ color: 'var(--accent)' }} />
            <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>
              Цель
            </h3>
          </div>
          <div className="flex gap-2">
            {goals.map((goal) => (
              <button
                key={goal.value}
                onClick={() => {
                  haptic('selection');
                  setLocalSettings((s) => ({ ...s, goal: goal.value }));
                }}
                className="flex-1 py-2 px-3 rounded-xl text-sm font-medium transition-all"
                style={{
                  background:
                    localSettings.goal === goal.value ? 'var(--accent)' : 'var(--bg-secondary)',
                  color: localSettings.goal === goal.value ? 'white' : 'var(--text-primary)',
                }}
              >
                {goal.label}
              </button>
            ))}
          </div>
        </Card>

        {/* Training type */}
        <Card>
          <div className="flex items-center gap-2 mb-3">
            <Dumbbell className="w-5 h-5" style={{ color: 'var(--accent)' }} />
            <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>
              Тренировки
            </h3>
          </div>
          <div className="flex gap-2 mb-3">
            {trainingTypes.map((type) => (
              <button
                key={type.value}
                onClick={() => {
                  haptic('selection');
                  setLocalSettings((s) => ({ ...s, training_type: type.value }));
                }}
                className="flex-1 py-2 px-3 rounded-xl text-sm font-medium transition-all"
                style={{
                  background:
                    localSettings.training_type === type.value
                      ? 'var(--accent)'
                      : 'var(--bg-secondary)',
                  color:
                    localSettings.training_type === type.value ? 'white' : 'var(--text-primary)',
                }}
              >
                {type.label}
              </button>
            ))}
          </div>

          <p className="text-xs mb-2" style={{ color: 'var(--text-secondary)' }}>
            Ритм дня
          </p>
          <div className="flex gap-2">
            {activityLevels.map((level) => (
              <button
                key={level.value}
                onClick={() => {
                  haptic('selection');
                  setLocalSettings((s) => ({ ...s, activity_level: level.value }));
                }}
                className="flex-1 py-2 px-3 rounded-xl text-sm font-medium transition-all"
                style={{
                  background:
                    localSettings.activity_level === level.value
                      ? 'var(--accent)'
                      : 'var(--bg-secondary)',
                  color:
                    localSettings.activity_level === level.value ? 'white' : 'var(--text-primary)',
                }}
              >
                {level.label}
              </button>
            ))}
          </div>
        </Card>

        {/* Features */}
        <Card>
          <h3 className="font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>
            Функции
          </h3>

          <div className="space-y-3">
            {/* Food tracker */}
            <div
              className="flex items-center justify-between p-3 rounded-xl cursor-pointer"
              style={{ background: 'var(--bg-secondary)' }}
              onClick={() => {
                haptic('selection');
                setLocalSettings((s) => ({
                  ...s,
                  food_tracker_enabled: !s.food_tracker_enabled,
                }));
              }}
            >
              <div className="flex items-center gap-3">
                <Utensils className="w-5 h-5" style={{ color: 'var(--accent)' }} />
                <span style={{ color: 'var(--text-primary)' }}>Food tracker</span>
              </div>
              <div
                className={`w-12 h-7 rounded-full p-1 transition-all ${
                  localSettings.food_tracker_enabled ? '' : ''
                }`}
                style={{
                  background: localSettings.food_tracker_enabled
                    ? 'var(--accent)'
                    : 'var(--border)',
                }}
              >
                <div
                  className={`w-5 h-5 rounded-full bg-white transition-transform ${
                    localSettings.food_tracker_enabled ? 'translate-x-5' : ''
                  }`}
                />
              </div>
            </div>

            {/* Sleep tracker */}
            <div
              className="flex items-center justify-between p-3 rounded-xl cursor-pointer"
              style={{ background: 'var(--bg-secondary)' }}
              onClick={() => {
                haptic('selection');
                setLocalSettings((s) => ({
                  ...s,
                  sleep_tracker_enabled: !s.sleep_tracker_enabled,
                }));
              }}
            >
              <div className="flex items-center gap-3">
                <Moon className="w-5 h-5" style={{ color: 'var(--accent)' }} />
                <span style={{ color: 'var(--text-primary)' }}>Трекер сна</span>
              </div>
              <div
                className="w-12 h-7 rounded-full p-1 transition-all"
                style={{
                  background: localSettings.sleep_tracker_enabled
                    ? 'var(--accent)'
                    : 'var(--border)',
                }}
              >
                <div
                  className={`w-5 h-5 rounded-full bg-white transition-transform ${
                    localSettings.sleep_tracker_enabled ? 'translate-x-5' : ''
                  }`}
                />
              </div>
            </div>

            {/* Weekly review */}
            <div
              className="flex items-center justify-between p-3 rounded-xl cursor-pointer"
              style={{ background: 'var(--bg-secondary)' }}
              onClick={() => {
                haptic('selection');
                setLocalSettings((s) => ({
                  ...s,
                  weekly_review_enabled: !s.weekly_review_enabled,
                }));
              }}
            >
              <div className="flex items-center gap-3">
                <Calendar className="w-5 h-5" style={{ color: 'var(--accent)' }} />
                <span style={{ color: 'var(--text-primary)' }}>Недельные обзоры</span>
              </div>
              <div
                className="w-12 h-7 rounded-full p-1 transition-all"
                style={{
                  background: localSettings.weekly_review_enabled
                    ? 'var(--accent)'
                    : 'var(--border)',
                }}
              >
                <div
                  className={`w-5 h-5 rounded-full bg-white transition-transform ${
                    localSettings.weekly_review_enabled ? 'translate-x-5' : ''
                  }`}
                />
              </div>
            </div>
          </div>
        </Card>

        {/* Time settings */}
        {(localSettings.food_tracker_enabled || localSettings.sleep_tracker_enabled) && (
          <Card>
            <div className="flex items-center gap-2 mb-3">
              <Clock className="w-5 h-5" style={{ color: 'var(--accent)' }} />
              <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                Время уведомлений
              </h3>
            </div>

            {localSettings.food_tracker_enabled && (
              <div className="mb-4">
                <label className="text-sm mb-2 block" style={{ color: 'var(--text-secondary)' }}>
                  Вечерний итог
                </label>
                <select
                  value={localSettings.evening_summary_time}
                  onChange={(e) =>
                    setLocalSettings((s) => ({ ...s, evening_summary_time: e.target.value }))
                  }
                  className="input-field"
                >
                  {timeOptions.evening.map((time) => (
                    <option key={time} value={time}>
                      {time}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {localSettings.sleep_tracker_enabled && (
              <div>
                <label className="text-sm mb-2 block" style={{ color: 'var(--text-secondary)' }}>
                  Утренний вопрос о сне
                </label>
                <select
                  value={localSettings.morning_question_time}
                  onChange={(e) =>
                    setLocalSettings((s) => ({ ...s, morning_question_time: e.target.value }))
                  }
                  className="input-field"
                >
                  {timeOptions.morning.map((time) => (
                    <option key={time} value={time}>
                      {time}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </Card>
        )}

        {/* Theme settings */}
        <Card>
          <div className="flex items-center gap-2 mb-3">
            <Palette className="w-5 h-5" style={{ color: 'var(--accent)' }} />
            <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>
              Оформление
            </h3>
          </div>

          {/* Theme mode */}
          <p className="text-xs mb-2" style={{ color: 'var(--text-secondary)' }}>
            Тема
          </p>
          <div className="flex gap-2 mb-4">
            {themeOptions.map((option) => (
              <button
                key={option.value}
                onClick={() => {
                  haptic('selection');
                  setThemeMode(option.value);
                }}
                className="flex-1 py-2 px-3 rounded-xl text-sm font-medium transition-all flex items-center justify-center gap-1"
                style={{
                  background:
                    themeMode === option.value ? 'var(--accent)' : 'var(--bg-secondary)',
                  color: themeMode === option.value ? 'white' : 'var(--text-primary)',
                }}
              >
                {option.value === 'light' && <Sun className="w-4 h-4" />}
                {option.value === 'dark' && <Moon className="w-4 h-4" />}
                {option.label}
              </button>
            ))}
          </div>

          {/* Color scheme */}
          <p className="text-xs mb-2" style={{ color: 'var(--text-secondary)' }}>
            Цветовая схема
          </p>
          <div className="flex gap-2">
            {colorSchemeOptions.map((option) => (
              <button
                key={option.value}
                onClick={() => {
                  haptic('selection');
                  setColorScheme(option.value);
                }}
                className="flex-1 py-2 px-3 rounded-xl text-sm font-medium transition-all flex items-center justify-center gap-2"
                style={{
                  background:
                    colorScheme === option.value ? 'var(--accent)' : 'var(--bg-secondary)',
                  color: colorScheme === option.value ? 'white' : 'var(--text-primary)',
                }}
              >
                <div
                  className="w-4 h-4 rounded-full"
                  style={{ background: option.color }}
                />
                {option.label}
              </button>
            ))}
          </div>
        </Card>

        {/* Save button */}
        <Button onClick={handleSave} loading={isSaving} className="w-full">
          <Check className="w-5 h-5 mr-2" />
          Сохранить
        </Button>
      </div>
    </Layout>
  );
}

export default Settings;
