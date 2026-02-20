// Achievements page - все достижения пользователя

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Layout, Card, LoadingSpinner } from '../components/Layout';
import { useTelegram } from '../hooks/useTelegram';
import { api } from '../api/client';
import type { Achievement } from '../types';
import { ArrowLeft, Trophy } from 'lucide-react';

export function Achievements() {
  const navigate = useNavigate();
  const { haptic } = useTelegram();
  const [achievements, setAchievements] = useState<Achievement[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    api.getAchievements()
      .then((data) => setAchievements(data.achievements || []))
      .catch(() => {})
      .finally(() => setIsLoading(false));
  }, []);

  const unlocked = achievements.filter((a) => a.unlocked);
  const locked = achievements.filter((a) => !a.unlocked);

  if (isLoading) {
    return (
      <Layout>
        <div className="flex items-center justify-center min-h-[60vh]">
          <LoadingSpinner size="lg" />
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => {
            haptic('light');
            navigate(-1);
          }}
          className="p-2 rounded-xl transition-colors"
          style={{ background: 'var(--bg-glass)' }}
        >
          <ArrowLeft className="w-5 h-5" style={{ color: 'var(--text-primary)' }} />
        </button>
        <div className="flex items-center gap-2">
          <Trophy className="w-5 h-5" style={{ color: 'var(--warning)' }} />
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
            Достижения
          </h1>
        </div>
        <span className="ml-auto text-sm" style={{ color: 'var(--text-tertiary)' }}>
          {unlocked.length}/{achievements.length}
        </span>
      </div>

      {unlocked.length > 0 && (
        <>
          <h2 className="text-sm font-medium mb-3" style={{ color: 'var(--text-secondary)' }}>
            Разблокированы
          </h2>
          <div className="grid grid-cols-2 gap-3 mb-6">
            {unlocked.map((a) => (
              <Card key={a.id} className="text-center">
                <div className="text-3xl mb-2">{a.icon}</div>
                <div className="font-semibold text-sm mb-1" style={{ color: 'var(--text-primary)' }}>
                  {a.name}
                </div>
                <div className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                  {a.description}
                </div>
                {a.unlocked_at && (
                  <div className="text-xs mt-1" style={{ color: 'var(--accent)' }}>
                    {new Date(a.unlocked_at).toLocaleDateString('ru-RU')}
                  </div>
                )}
              </Card>
            ))}
          </div>
        </>
      )}

      {locked.length > 0 && (
        <>
          <h2 className="text-sm font-medium mb-3" style={{ color: 'var(--text-secondary)' }}>
            Заблокированы
          </h2>
          <div className="grid grid-cols-2 gap-3">
            {locked.map((a) => (
              <Card key={a.id} className="text-center opacity-50">
                <div className="text-3xl mb-2 grayscale">{a.icon}</div>
                <div className="font-semibold text-sm mb-1" style={{ color: 'var(--text-primary)' }}>
                  {a.name}
                </div>
                <div className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                  {a.description}
                </div>
              </Card>
            ))}
          </div>
        </>
      )}
    </Layout>
  );
}

export default Achievements;
