// Sleep tracker page - rate your sleep

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Layout, Button } from '../components/Layout';
import { useTelegram } from '../hooks/useTelegram';
import { api } from '../api/client';
import { Moon, ArrowLeft, Check } from 'lucide-react';

const sleepLabels = [
  { score: 1, emoji: '😴', label: 'Очень плохо' },
  { score: 2, emoji: '😕', label: 'Плохо' },
  { score: 3, emoji: '😐', label: 'Нормально' },
  { score: 4, emoji: '🙂', label: 'Хорошо' },
  { score: 5, emoji: '😊', label: 'Отлично' },
];

export function Sleep() {
  const navigate = useNavigate();
  const { haptic } = useTelegram();
  const [selectedScore, setSelectedScore] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSelect = (score: number) => {
    haptic('selection');
    setSelectedScore(score);
  };

  const handleSubmit = async () => {
    if (!selectedScore) return;

    setIsLoading(true);
    setError(null);
    haptic('medium');

    try {
      await api.addSleepEntry(selectedScore);
      haptic('success');
      navigate('/');
    } catch (err) {
      console.error('Failed to save sleep:', err);
      setError('Не удалось сохранить');
      haptic('error');
    } finally {
      setIsLoading(false);
    }
  };

  const selectedLabel = sleepLabels.find((l) => l.score === selectedScore);

  return (
    <Layout>
      <div className="flex items-center gap-3 mb-8">
        <button
          onClick={() => navigate(-1)}
          className="p-2 rounded-xl transition-colors"
          style={{ background: 'var(--bg-glass)' }}
        >
          <ArrowLeft className="w-5 h-5" style={{ color: 'var(--text-primary)' }} />
        </button>
        <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
          Трекер сна
        </h1>
      </div>

      <div className="text-center pt-8 animate-in">
        <div
          className="w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6"
          style={{ background: 'var(--accent-soft)' }}
        >
          <Moon className="w-10 h-10" style={{ color: 'var(--accent)' }} />
        </div>

        <h2 className="text-2xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>
          Как ты сегодня спал?
        </h2>
        <p className="text-sm mb-10" style={{ color: 'var(--text-secondary)' }}>
          Оцени качество своего сна
        </p>

        {/* Score buttons */}
        <div className="flex justify-center gap-3 mb-8">
          {sleepLabels.map(({ score, emoji }) => (
            <button
              key={score}
              onClick={() => handleSelect(score)}
              className={`w-14 h-14 rounded-full text-2xl transition-all ${
                selectedScore === score
                  ? 'scale-110 shadow-lg'
                  : 'opacity-60 hover:opacity-100'
              }`}
              style={{
                background:
                  selectedScore === score ? 'var(--accent)' : 'var(--bg-glass)',
                border: `2px solid ${
                  selectedScore === score ? 'var(--accent)' : 'var(--border)'
                }`,
              }}
            >
              {emoji}
            </button>
          ))}
        </div>

        {/* Selected label */}
        {selectedLabel && (
          <div
            className="text-lg font-medium mb-8 slide-up"
            style={{ color: 'var(--text-primary)' }}
          >
            {selectedLabel.label}
          </div>
        )}

        {/* Error */}
        {error && (
          <div
            className="p-3 rounded-xl mb-4 text-sm"
            style={{ background: 'var(--error-soft)', color: 'var(--error)' }}
          >
            {error}
          </div>
        )}

        {/* Submit button */}
        <Button
          onClick={handleSubmit}
          loading={isLoading}
          disabled={!selectedScore}
          className="w-full"
        >
          <Check className="w-5 h-5 mr-2" />
          Сохранить
        </Button>
      </div>
    </Layout>
  );
}

export default Sleep;
