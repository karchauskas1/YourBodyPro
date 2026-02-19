// Settings page - edit profile and preferences

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Layout, Card, Button } from '../components/Layout';
import { useStore } from '../store/useStore';
import { useTelegram } from '../hooks/useTelegram';
import { useTheme, themeOptions, colorSchemeOptions } from '../hooks/useTheme';
import { api } from '../api/client';
import {
  ArrowLeft,
  Utensils,
  Moon,
  Calendar,
  Clock,
  Check,
  Palette,
  Sun,
  RefreshCw,
  Gift,
  Copy,
  Trophy,
} from 'lucide-react';

export function Settings() {
  const navigate = useNavigate();
  const { haptic } = useTelegram();
  const { profile, setProfile } = useStore();
  const { themeMode, colorScheme, setThemeMode, setColorScheme } = useTheme();

  const [isSaving, setIsSaving] = useState(false);
  const [autoRenewal, setAutoRenewal] = useState<{ enabled: boolean; has_payment_method: boolean } | null>(null);
  const [referralInfo, setReferralInfo] = useState<{
    code: string; link: string;
    stats: { total_invited: number; total_paid: number; available_rewards: number };
  } | null>(null);
  const [copied, setCopied] = useState(false);
  const [localSettings, setLocalSettings] = useState({
    food_tracker_enabled: profile?.food_tracker_enabled || false,
    sleep_tracker_enabled: profile?.sleep_tracker_enabled || false,
    weekly_review_enabled: profile?.weekly_review_enabled || false,
    evening_summary_time: profile?.evening_summary_time || '21:00',
    morning_question_time: profile?.morning_question_time || '08:00',
  });

  useEffect(() => {
    if (profile) {
      setLocalSettings({
        food_tracker_enabled: profile.food_tracker_enabled,
        sleep_tracker_enabled: profile.sleep_tracker_enabled,
        weekly_review_enabled: profile.weekly_review_enabled,
        evening_summary_time: profile.evening_summary_time,
        morning_question_time: profile.morning_question_time,
      });
    }
  }, [profile]);

  useEffect(() => {
    api.getAutoRenewalStatus().then(setAutoRenewal).catch(() => {});
    api.getReferralInfo().then(setReferralInfo).catch(() => {});
  }, []);

  const handleSave = async () => {
    setIsSaving(true);
    haptic('medium');

    try {
      // Получаем timezone offset пользователя (в минутах от UTC)
      // JavaScript возвращает offset с обратным знаком, поэтому инвертируем
      const timezoneOffset = -new Date().getTimezoneOffset();

      await api.updateSettings({
        ...localSettings,
        timezone_offset: timezoneOffset,
      });

      // Update local profile
      if (profile) {
        setProfile({
          ...profile,
          ...localSettings,
          timezone_offset: timezoneOffset,
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

        {/* Subscription - Auto-renewal */}
        {autoRenewal && (
          <Card>
            <div className="flex items-center gap-2 mb-3">
              <RefreshCw className="w-5 h-5" style={{ color: 'var(--accent)' }} />
              <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                Подписка
              </h3>
            </div>

            <div
              className="flex items-center justify-between p-3 rounded-xl cursor-pointer"
              style={{ background: 'var(--bg-secondary)' }}
              onClick={async () => {
                if (!autoRenewal.has_payment_method) return;
                haptic('selection');
                try {
                  const result = await api.toggleAutoRenewal();
                  setAutoRenewal({ ...autoRenewal, enabled: result.enabled });
                } catch (err) {
                  console.error('Toggle auto-renewal failed:', err);
                }
              }}
            >
              <div className="flex-1 min-w-0">
                <span style={{ color: 'var(--text-primary)' }}>Автопродление</span>
                {!autoRenewal.has_payment_method && (
                  <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>
                    Активируется после оплаты
                  </p>
                )}
              </div>
              <div
                className="w-12 h-7 rounded-full p-1 transition-all"
                style={{
                  background: autoRenewal.enabled ? 'var(--accent)' : 'var(--border)',
                  opacity: autoRenewal.has_payment_method ? 1 : 0.5,
                }}
              >
                <div
                  className={`w-5 h-5 rounded-full bg-white transition-transform ${
                    autoRenewal.enabled ? 'translate-x-5' : ''
                  }`}
                />
              </div>
            </div>
          </Card>
        )}

        {/* Referral Program */}
        {referralInfo && (
          <Card>
            <div className="flex items-center gap-2 mb-3">
              <Gift className="w-5 h-5" style={{ color: 'var(--accent)' }} />
              <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                Реферальная программа
              </h3>
            </div>

            <p className="text-sm mb-3" style={{ color: 'var(--text-secondary)' }}>
              Пригласи друга — получи скидку 30% на следующий месяц
            </p>

            <div
              className="flex items-center gap-2 p-3 rounded-xl mb-3 cursor-pointer"
              style={{ background: 'var(--bg-secondary)' }}
              onClick={() => {
                navigator.clipboard.writeText(referralInfo.link);
                setCopied(true);
                haptic('success');
                setTimeout(() => setCopied(false), 2000);
              }}
            >
              <span className="flex-1 text-sm truncate" style={{ color: 'var(--text-primary)' }}>
                {referralInfo.link}
              </span>
              <Copy className="w-4 h-4 flex-shrink-0" style={{ color: copied ? 'var(--success)' : 'var(--text-tertiary)' }} />
            </div>

            <div className="flex gap-3 text-center">
              <div className="flex-1 p-2 rounded-xl" style={{ background: 'var(--bg-secondary)' }}>
                <div className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>
                  {referralInfo.stats.total_invited}
                </div>
                <div className="text-xs" style={{ color: 'var(--text-tertiary)' }}>Приглашено</div>
              </div>
              <div className="flex-1 p-2 rounded-xl" style={{ background: 'var(--bg-secondary)' }}>
                <div className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>
                  {referralInfo.stats.total_paid}
                </div>
                <div className="text-xs" style={{ color: 'var(--text-tertiary)' }}>Оплатили</div>
              </div>
              <div className="flex-1 p-2 rounded-xl" style={{ background: 'var(--bg-secondary)' }}>
                <div className="text-lg font-bold" style={{ color: 'var(--accent)' }}>
                  {referralInfo.stats.available_rewards}
                </div>
                <div className="text-xs" style={{ color: 'var(--text-tertiary)' }}>Скидки</div>
              </div>
            </div>
          </Card>
        )}

        {/* Achievements link */}
        <Card
          className="cursor-pointer"
          onClick={() => {
            haptic('light');
            navigate('/achievements');
          }}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Trophy className="w-5 h-5" style={{ color: 'var(--warning)' }} />
              <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                Достижения
              </span>
            </div>
            <ArrowLeft className="w-5 h-5 rotate-180" style={{ color: 'var(--text-tertiary)' }} />
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
                className="flex-1 py-2 px-2 rounded-xl text-xs font-medium transition-all flex items-center justify-center gap-1 min-w-0"
                style={{
                  background:
                    colorScheme === option.value ? 'var(--accent)' : 'var(--bg-secondary)',
                  color: colorScheme === option.value ? 'white' : 'var(--text-primary)',
                }}
              >
                <div
                  className="w-3 h-3 rounded-full flex-shrink-0"
                  style={{ background: option.color }}
                />
                <span className="truncate">{option.label}</span>
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
