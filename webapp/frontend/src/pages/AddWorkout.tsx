// Add Workout page - mark workout with name, duration, and intensity

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Layout, Button } from '../components/Layout';
import { useTelegram } from '../hooks/useTelegram';
import { api } from '../api/client';
import { ArrowLeft, Check, Dumbbell } from 'lucide-react';

export function AddWorkout() {
  const navigate = useNavigate();
  const { haptic } = useTelegram();

  const [workoutName, setWorkoutName] = useState('');
  const [durationMinutes, setDurationMinutes] = useState<number | ''>('');
  const [intensity, setIntensity] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const intensityLabels = [
    { level: 1, label: 'Легко', emoji: '😌' },
    { level: 2, label: 'Легко+', emoji: '🙂' },
    { level: 3, label: 'Средне', emoji: '😊' },
    { level: 4, label: 'Интенсивно', emoji: '💪' },
    { level: 5, label: 'Очень интенсивно', emoji: '🔥' },
  ];

  const handleSubmit = async () => {
    if (!workoutName.trim()) {
      setError('Укажите название тренировки');
      haptic('error');
      return;
    }

    if (!durationMinutes || durationMinutes <= 0) {
      setError('Укажите длительность тренировки');
      haptic('error');
      return;
    }

    if (!intensity) {
      setError('Укажите интенсивность тренировки');
      haptic('error');
      return;
    }

    setIsLoading(true);
    setError(null);
    haptic('medium');

    try {
      await api.addWorkout(workoutName.trim(), Number(durationMinutes), intensity);
      haptic('success');
      navigate('/');
    } catch (err: any) {
      console.error('Failed to add workout:', err);
      setError(err?.message || 'Не удалось сохранить тренировку');
      haptic('error');
    } finally {
      setIsLoading(false);
    }
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
          Отметить тренировку
        </h1>
      </div>

      <div className="animate-in">
        {/* Workout name */}
        <div className="mb-6">
          <label
            className="block text-sm font-medium mb-2"
            style={{ color: 'var(--text-secondary)' }}
          >
            Название тренировки
          </label>
          <input
            type="text"
            value={workoutName}
            onChange={(e) => setWorkoutName(e.target.value)}
            placeholder="Например: Силовая, Йога, Бег"
            className="input-field"
            autoFocus
          />
        </div>

        {/* Duration */}
        <div className="mb-6">
          <label
            className="block text-sm font-medium mb-2"
            style={{ color: 'var(--text-secondary)' }}
          >
            Длительность (минуты)
          </label>
          <input
            type="number"
            value={durationMinutes}
            onChange={(e) => setDurationMinutes(e.target.value === '' ? '' : Number(e.target.value))}
            placeholder="45"
            min="1"
            className="input-field"
          />
          <p className="text-xs mt-2" style={{ color: 'var(--text-tertiary)' }}>
            Укажите продолжительность тренировки в минутах
          </p>
        </div>

        {/* Intensity */}
        <div className="mb-6">
          <label
            className="text-sm font-medium mb-3 block"
            style={{ color: 'var(--text-secondary)' }}
          >
            Интенсивность
          </label>
          <div className="space-y-2">
            {intensityLabels.map((item) => (
              <button
                key={item.level}
                onClick={() => {
                  haptic('selection');
                  setIntensity(intensity === item.level ? null : item.level);
                }}
                className="w-full py-3 px-4 rounded-xl text-sm font-medium transition-all flex items-center justify-between"
                style={{
                  background: intensity === item.level ? 'var(--accent)' : 'var(--bg-secondary)',
                  color: intensity === item.level ? 'white' : 'var(--text-primary)',
                }}
              >
                <div className="flex items-center gap-3">
                  <span className="text-xl">{item.emoji}</span>
                  <span>{item.label}</span>
                </div>
                {intensity === item.level && <Check className="w-5 h-5" />}
              </button>
            ))}
          </div>
          <p className="text-xs mt-2" style={{ color: 'var(--text-tertiary)' }}>
            1 - легкая разминка, 5 - максимальная нагрузка
          </p>
        </div>

        {error && (
          <div
            className="p-3 rounded-xl mb-4 text-sm"
            style={{ background: 'var(--error-soft)', color: 'var(--error)' }}
          >
            {error}
          </div>
        )}

        <Button
          onClick={handleSubmit}
          loading={isLoading}
          disabled={!workoutName.trim() || !durationMinutes || !intensity}
          className="w-full"
        >
          <Dumbbell className="w-5 h-5 mr-2" />
          Сохранить тренировку
        </Button>
      </div>
    </Layout>
  );
}

export default AddWorkout;
