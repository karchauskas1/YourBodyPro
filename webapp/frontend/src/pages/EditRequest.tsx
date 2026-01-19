// Edit Request page - edit goal, training type, activity level

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Layout, Card, Button } from '../components/Layout';
import { useStore } from '../store/useStore';
import { useTelegram } from '../hooks/useTelegram';
import { api } from '../api/client';
import type { Goal, TrainingType, ActivityLevel } from '../types';
import {
  ArrowLeft,
  Target,
  Dumbbell,
  Activity,
  Check
} from 'lucide-react';

export function EditRequest() {
  const navigate = useNavigate();
  const { haptic } = useTelegram();
  const { profile, setProfile } = useStore();

  const [isSaving, setIsSaving] = useState(false);
  const [localSettings, setLocalSettings] = useState({
    goal: profile?.goal || 'maintain' as Goal,
    training_type: profile?.training_type || 'marathon' as TrainingType,
    activity_level: profile?.activity_level || 'medium' as ActivityLevel,
  });

  useEffect(() => {
    if (profile) {
      setLocalSettings({
        goal: profile.goal || 'maintain',
        training_type: profile.training_type || 'marathon',
        activity_level: profile.activity_level || 'medium',
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
    { value: 'calm', label: 'Спокойный' },
    { value: 'medium', label: 'Средний' },
    { value: 'active', label: 'Активный' },
  ];

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
          Изменить запрос
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
          <div className="flex gap-2">
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
        </Card>

        {/* Activity level */}
        <Card>
          <div className="flex items-center gap-2 mb-3">
            <Activity className="w-5 h-5" style={{ color: 'var(--accent)' }} />
            <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>
              Ритм дня
            </h3>
          </div>
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

        {/* Save button */}
        <Button onClick={handleSave} loading={isSaving} className="w-full">
          <Check className="w-5 h-5 mr-2" />
          Сохранить
        </Button>
      </div>
    </Layout>
  );
}

export default EditRequest;
