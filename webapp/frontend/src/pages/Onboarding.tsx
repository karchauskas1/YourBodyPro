// Onboarding flow - 4 screens

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Layout, Button, Card } from '../components/Layout';
import { useStore } from '../store/useStore';
import { useTelegram } from '../hooks/useTelegram';
import { api } from '../api/client';
import type { Goal, TrainingType, ActivityLevel, OnboardingData } from '../types';
import {
  Target,
  Dumbbell,
  Utensils,
  Moon,
  Calendar,
  ChevronRight,
  Check
} from 'lucide-react';

// Step 1: Welcome
function WelcomeStep({ onNext }: { onNext: () => void }) {
  const { haptic } = useTelegram();

  return (
    <div className="animate-in flex flex-col items-center text-center pt-12">
      <div
        className="w-20 h-20 rounded-full flex items-center justify-center mb-8"
        style={{ background: 'var(--accent-soft)' }}
      >
        <span className="text-4xl">✨</span>
      </div>

      <h1 className="text-2xl font-bold mb-4" style={{ color: 'var(--text-primary)' }}>
        Привет!
      </h1>

      <p className="text-base mb-2" style={{ color: 'var(--text-secondary)' }}>
        Я помогу тебе освоить полезные привычки
      </p>

      <p className="text-sm mb-12" style={{ color: 'var(--text-tertiary)' }}>
        Без давления, подсчётов и постоянных напоминаний
      </p>

      <Button
        onClick={() => {
          haptic('light');
          onNext();
        }}
        className="w-full"
      >
        Начать
        <ChevronRight className="inline-block ml-2 w-5 h-5" />
      </Button>
    </div>
  );
}

// Step 2: Goal selection
function GoalStep({
  value,
  onChange,
  onNext
}: {
  value: Goal | null;
  onChange: (goal: Goal) => void;
  onNext: () => void;
}) {
  const { haptic } = useTelegram();

  const goals: { value: Goal; label: string; description: string }[] = [
    { value: 'maintain', label: 'Поддержание', description: 'Сохранить текущую форму' },
    { value: 'lose', label: 'Снижение', description: 'Снизить вес' },
    { value: 'gain', label: 'Набор', description: 'Набрать массу' },
  ];

  return (
    <div className="animate-in">
      <div className="text-center mb-8">
        <div
          className="w-14 h-14 rounded-full flex items-center justify-center mx-auto mb-4"
          style={{ background: 'var(--accent-soft)' }}
        >
          <Target className="w-7 h-7" style={{ color: 'var(--accent)' }} />
        </div>
        <h2 className="text-xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>
          Твоя цель
        </h2>
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
          Это поможет настроить анализ питания
        </p>
      </div>

      <div className="space-y-3 mb-8">
        {goals.map((goal) => (
          <div
            key={goal.value}
            className={`option-card ${value === goal.value ? 'selected' : ''}`}
            onClick={() => {
              haptic('selection');
              onChange(goal.value);
            }}
          >
            <div className="flex items-center justify-between">
              <div>
                <div className="font-medium" style={{ color: 'var(--text-primary)' }}>
                  {goal.label}
                </div>
                <div className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                  {goal.description}
                </div>
              </div>
              {value === goal.value && (
                <Check className="w-5 h-5" style={{ color: 'var(--accent)' }} />
              )}
            </div>
          </div>
        ))}
      </div>

      <Button onClick={onNext} disabled={!value} className="w-full">
        Далее
        <ChevronRight className="inline-block ml-2 w-5 h-5" />
      </Button>
    </div>
  );
}

// Step 3: Training type & activity
function TrainingStep({
  trainingType,
  activityLevel,
  onChangeTraining,
  onChangeActivity,
  onNext,
}: {
  trainingType: TrainingType | null;
  activityLevel: ActivityLevel | null;
  onChangeTraining: (type: TrainingType) => void;
  onChangeActivity: (level: ActivityLevel) => void;
  onNext: () => void;
}) {
  const { haptic } = useTelegram();

  const trainingTypes: { value: TrainingType; label: string }[] = [
    { value: 'marathon', label: 'Марафон с Настей' },
    { value: 'own', label: 'Свои тренировки' },
    { value: 'mixed', label: 'Смешанный формат' },
  ];

  const activityLevels: { value: ActivityLevel; label: string; description: string }[] = [
    { value: 'active', label: 'Активный', description: 'Много движения в течение дня' },
    { value: 'medium', label: 'Средний', description: 'Умеренная активность' },
    { value: 'calm', label: 'Спокойный', description: 'Преимущественно сидячий' },
  ];

  return (
    <div className="animate-in">
      <div className="text-center mb-6">
        <div
          className="w-14 h-14 rounded-full flex items-center justify-center mx-auto mb-4"
          style={{ background: 'var(--accent-soft)' }}
        >
          <Dumbbell className="w-7 h-7" style={{ color: 'var(--accent)' }} />
        </div>
        <h2 className="text-xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>
          Тренировки
        </h2>
      </div>

      <div className="space-y-2 mb-6">
        {trainingTypes.map((type) => (
          <div
            key={type.value}
            className={`option-card py-3 ${trainingType === type.value ? 'selected' : ''}`}
            onClick={() => {
              haptic('selection');
              onChangeTraining(type.value);
            }}
          >
            <div className="flex items-center justify-between">
              <span className="font-medium" style={{ color: 'var(--text-primary)' }}>
                {type.label}
              </span>
              {trainingType === type.value && (
                <Check className="w-5 h-5" style={{ color: 'var(--accent)' }} />
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="mb-6">
        <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--text-secondary)' }}>
          Ритм дня
        </h3>
        <div className="flex gap-2">
          {activityLevels.map((level) => (
            <button
              key={level.value}
              className={`flex-1 py-2 px-3 rounded-xl text-sm font-medium transition-all ${
                activityLevel === level.value
                  ? 'text-white'
                  : ''
              }`}
              style={{
                background: activityLevel === level.value ? 'var(--accent)' : 'var(--bg-glass)',
                color: activityLevel === level.value ? 'white' : 'var(--text-primary)',
                border: `1px solid ${activityLevel === level.value ? 'var(--accent)' : 'var(--border)'}`,
              }}
              onClick={() => {
                haptic('selection');
                onChangeActivity(level.value);
              }}
            >
              {level.label}
            </button>
          ))}
        </div>
      </div>

      <Button
        onClick={onNext}
        disabled={!trainingType || !activityLevel}
        className="w-full"
      >
        Далее
        <ChevronRight className="inline-block ml-2 w-5 h-5" />
      </Button>
    </div>
  );
}

// Step 4: Features selection
function FeaturesStep({
  data,
  onChange,
  onComplete,
  isLoading,
}: {
  data: {
    food_tracker_enabled: boolean;
    sleep_tracker_enabled: boolean;
    weekly_review_enabled: boolean;
    evening_summary_time: string;
    morning_question_time: string;
  };
  onChange: (updates: Partial<typeof data>) => void;
  onComplete: () => void;
  isLoading: boolean;
}) {
  const { haptic } = useTelegram();

  const features = [
    {
      key: 'food_tracker_enabled' as const,
      icon: Utensils,
      label: 'Food tracker',
      description: 'Фото/текст еды → вечерний анализ',
    },
    {
      key: 'sleep_tracker_enabled' as const,
      icon: Moon,
      label: 'Трекер сна',
      description: 'Утренний вопрос о качестве сна',
    },
    {
      key: 'weekly_review_enabled' as const,
      icon: Calendar,
      label: 'Недельные обзоры',
      description: 'Паттерны и связи каждое воскресенье',
    },
  ];

  const timeOptions = [
    '06:00', '07:00', '08:00', '09:00', '10:00', '11:00',
    '18:00', '19:00', '20:00', '21:00', '22:00', '23:00',
  ];

  return (
    <div className="animate-in">
      <div className="text-center mb-6">
        <h2 className="text-xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>
          Что включить?
        </h2>
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
          Выбери функции, которые тебе нужны
        </p>
      </div>

      <div className="space-y-3 mb-6">
        {features.map((feature) => {
          const Icon = feature.icon;
          const isEnabled = data[feature.key];

          return (
            <div
              key={feature.key}
              className={`option-card ${isEnabled ? 'selected' : ''}`}
              onClick={() => {
                haptic('selection');
                onChange({ [feature.key]: !isEnabled });
              }}
            >
              <div className="flex items-center gap-3">
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center"
                  style={{
                    background: isEnabled ? 'var(--accent)' : 'var(--bg-secondary)',
                  }}
                >
                  <Icon
                    className="w-5 h-5"
                    style={{ color: isEnabled ? 'white' : 'var(--text-secondary)' }}
                  />
                </div>
                <div className="flex-1">
                  <div className="font-medium" style={{ color: 'var(--text-primary)' }}>
                    {feature.label}
                  </div>
                  <div className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                    {feature.description}
                  </div>
                </div>
                <div
                  className={`w-6 h-6 rounded-full border-2 flex items-center justify-center transition-all ${
                    isEnabled ? 'border-transparent' : ''
                  }`}
                  style={{
                    background: isEnabled ? 'var(--accent)' : 'transparent',
                    borderColor: isEnabled ? 'var(--accent)' : 'var(--border)',
                  }}
                >
                  {isEnabled && <Check className="w-4 h-4 text-white" />}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Time settings */}
      {(data.food_tracker_enabled || data.sleep_tracker_enabled) && (
        <Card className="mb-6">
          <h3 className="text-sm font-medium mb-4" style={{ color: 'var(--text-secondary)' }}>
            Настройки времени
          </h3>

          {data.food_tracker_enabled && (
            <div className="mb-4">
              <label className="text-sm mb-2 block" style={{ color: 'var(--text-primary)' }}>
                Вечерний итог
              </label>
              <select
                value={data.evening_summary_time}
                onChange={(e) => onChange({ evening_summary_time: e.target.value })}
                className="input-field"
              >
                {timeOptions.filter(t => parseInt(t) >= 18).map((time) => (
                  <option key={time} value={time}>{time}</option>
                ))}
              </select>
            </div>
          )}

          {data.sleep_tracker_enabled && (
            <div>
              <label className="text-sm mb-2 block" style={{ color: 'var(--text-primary)' }}>
                Утренний вопрос о сне
              </label>
              <select
                value={data.morning_question_time}
                onChange={(e) => onChange({ morning_question_time: e.target.value })}
                className="input-field"
              >
                {timeOptions.filter(t => parseInt(t) <= 11).map((time) => (
                  <option key={time} value={time}>{time}</option>
                ))}
              </select>
            </div>
          )}
        </Card>
      )}

      <Button onClick={onComplete} loading={isLoading} className="w-full">
        Готово
        <Check className="inline-block ml-2 w-5 h-5" />
      </Button>
    </div>
  );
}

// Main Onboarding component
export function Onboarding() {
  const navigate = useNavigate();
  const { haptic } = useTelegram();
  const { onboardingData, updateOnboardingData, setProfile } = useStore();
  const [step, setStep] = useState(0);
  const [isLoading, setIsLoading] = useState(false);

  const totalSteps = 4;

  const handleNext = () => {
    haptic('light');
    setStep((s) => s + 1);
  };

  const handleComplete = async () => {
    if (!onboardingData.goal || !onboardingData.training_type || !onboardingData.activity_level) {
      return;
    }

    setIsLoading(true);
    haptic('medium');

    try {
      // Получаем timezone offset пользователя (в минутах от UTC)
      const timezoneOffset = -new Date().getTimezoneOffset();

      const data: OnboardingData = {
        goal: onboardingData.goal,
        training_type: onboardingData.training_type,
        activity_level: onboardingData.activity_level,
        food_tracker_enabled: onboardingData.food_tracker_enabled,
        sleep_tracker_enabled: onboardingData.sleep_tracker_enabled,
        weekly_review_enabled: onboardingData.weekly_review_enabled,
        evening_summary_time: onboardingData.evening_summary_time,
        morning_question_time: onboardingData.morning_question_time,
        timezone_offset: timezoneOffset,
      };

      await api.saveOnboarding(data);

      // Update local profile
      setProfile({
        user_id: 0, // Will be set by backend
        ...data,
        onboarding_completed: true,
      });

      haptic('success');
      navigate('/');
    } catch (error) {
      console.error('Failed to save onboarding:', error);
      haptic('error');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Layout>
      {/* Progress bar */}
      {step > 0 && (
        <div className="mb-6">
          <div className="progress-bar">
            <div
              className="progress-bar-fill"
              style={{ width: `${(step / (totalSteps - 1)) * 100}%` }}
            />
          </div>
          <div className="text-xs mt-2 text-center" style={{ color: 'var(--text-tertiary)' }}>
            {step} из {totalSteps - 1}
          </div>
        </div>
      )}

      {/* Steps */}
      {step === 0 && <WelcomeStep onNext={handleNext} />}

      {step === 1 && (
        <GoalStep
          value={onboardingData.goal}
          onChange={(goal) => updateOnboardingData({ goal })}
          onNext={handleNext}
        />
      )}

      {step === 2 && (
        <TrainingStep
          trainingType={onboardingData.training_type}
          activityLevel={onboardingData.activity_level}
          onChangeTraining={(training_type) => updateOnboardingData({ training_type })}
          onChangeActivity={(activity_level) => updateOnboardingData({ activity_level })}
          onNext={handleNext}
        />
      )}

      {step === 3 && (
        <FeaturesStep
          data={{
            food_tracker_enabled: onboardingData.food_tracker_enabled,
            sleep_tracker_enabled: onboardingData.sleep_tracker_enabled,
            weekly_review_enabled: onboardingData.weekly_review_enabled,
            evening_summary_time: onboardingData.evening_summary_time,
            morning_question_time: onboardingData.morning_question_time,
          }}
          onChange={updateOnboardingData}
          onComplete={handleComplete}
          isLoading={isLoading}
        />
      )}
    </Layout>
  );
}

export default Onboarding;
