// Weekly Summary page - patterns and insights

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { format, addDays } from 'date-fns';
import { ru } from 'date-fns/locale';
import { Layout, Card, Button, LoadingSpinner, EmptyState } from '../components/Layout';
import { api } from '../api/client';
import type { WeeklySummary as WeeklySummaryType } from '../types';
import { ArrowLeft, BarChart3, Moon, Lightbulb, TrendingUp } from 'lucide-react';

// Diversity bar visualization
function DiversityBar({ level }: { level: string }) {
  const levels: Record<string, { width: string; color: string }> = {
    'высокое': { width: '100%', color: 'var(--success)' },
    'среднее': { width: '66%', color: 'var(--warning)' },
    'низкое': { width: '33%', color: 'var(--error)' },
  };

  const config = levels[level] || levels['среднее'];

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 rounded-full" style={{ background: 'var(--border)' }}>
        <div
          className="h-full rounded-full transition-all"
          style={{ width: config.width, background: config.color }}
        />
      </div>
      <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
        {level}
      </span>
    </div>
  );
}

// Sleep visualization
function SleepChart({ average }: { average: number | null }) {
  if (average === null) {
    return (
      <div className="text-sm" style={{ color: 'var(--text-tertiary)' }}>
        Нет данных
      </div>
    );
  }

  const percentage = (average / 5) * 100;

  return (
    <div className="flex items-center gap-3">
      <div className="flex-1">
        <div className="h-3 rounded-full" style={{ background: 'var(--border)' }}>
          <div
            className="h-full rounded-full transition-all"
            style={{
              width: `${percentage}%`,
              background:
                average >= 4 ? 'var(--success)' : average >= 3 ? 'var(--warning)' : 'var(--error)',
            }}
          />
        </div>
      </div>
      <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>
        {average.toFixed(1)}/5
      </span>
    </div>
  );
}

export function WeeklySummary() {
  const navigate = useNavigate();
  const [summary, setSummary] = useState<WeeklySummaryType | null>(null);
  const [weekStart, setWeekStart] = useState<string>('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [noData, setNoData] = useState(false);

  useEffect(() => {
    loadSummary();
  }, []);

  const loadSummary = async () => {
    try {
      setIsLoading(true);
      setError(null);
      setNoData(false);

      const response = await api.getCurrentWeekly();

      if (!response.summary) {
        setNoData(true);
      } else {
        setSummary(response.summary);
        setWeekStart(response.week_start);
      }
    } catch (err) {
      console.error('Failed to load weekly summary:', err);
      setError('Не удалось загрузить обзор');
    } finally {
      setIsLoading(false);
    }
  };

  // Calculate week range for display
  const getWeekRange = () => {
    if (!weekStart) return '';
    const start = new Date(weekStart);
    const end = addDays(start, 6);
    return `${format(start, 'd', { locale: ru })}–${format(end, 'd MMMM', { locale: ru })}`;
  };

  // Day names for chart
  const dayNames = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

  if (isLoading) {
    return (
      <Layout>
        <div className="flex flex-col items-center justify-center min-h-[60vh]">
          <LoadingSpinner size="lg" />
          <p className="mt-4 text-sm" style={{ color: 'var(--text-secondary)' }}>
            Собираем аналитику...
          </p>
        </div>
      </Layout>
    );
  }

  if (error) {
    return (
      <Layout>
        <EmptyState
          title="Ошибка"
          description={error}
          action={
            <Button onClick={loadSummary} variant="secondary">
              Попробовать снова
            </Button>
          }
        />
      </Layout>
    );
  }

  if (noData) {
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
            Недельный обзор
          </h1>
        </div>

        <EmptyState
          icon={<BarChart3 className="w-12 h-12" />}
          title="Недостаточно данных"
          description="Добавляй еду и отмечай сон в течение недели, чтобы получить обзор"
          action={
            <Button onClick={() => navigate('/')}>
              На главную
            </Button>
          }
        />
      </Layout>
    );
  }

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
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
            Недельный обзор
          </h1>
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
            {getWeekRange()}
          </p>
        </div>
      </div>

      <div className="space-y-4 animate-in">
        {/* Food diversity by day */}
        {summary?.food_diversity_by_day && Object.keys(summary.food_diversity_by_day).length > 0 && (
          <Card>
            <div className="flex items-center gap-2 mb-4">
              <BarChart3 className="w-5 h-5" style={{ color: 'var(--accent)' }} />
              <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                Питание
              </h3>
            </div>

            <div className="space-y-3">
              {Object.entries(summary.food_diversity_by_day).map(([day, level], index) => (
                <div key={day} className="flex items-center gap-3">
                  <span
                    className="w-8 text-sm font-medium"
                    style={{ color: 'var(--text-secondary)' }}
                  >
                    {dayNames[index] || day}
                  </span>
                  <div className="flex-1">
                    <DiversityBar level={level} />
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* Sleep average */}
        {summary?.sleep_average !== undefined && (
          <Card>
            <div className="flex items-center gap-2 mb-4">
              <Moon className="w-5 h-5" style={{ color: 'var(--accent)' }} />
              <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                Сон
              </h3>
            </div>

            <div>
              <p className="text-sm mb-2" style={{ color: 'var(--text-secondary)' }}>
                Средняя оценка
              </p>
              <SleepChart average={summary.sleep_average} />
            </div>
          </Card>
        )}

        {/* Patterns */}
        {summary?.patterns && summary.patterns.length > 0 && (
          <Card>
            <div className="flex items-center gap-2 mb-4">
              <TrendingUp className="w-5 h-5" style={{ color: 'var(--accent)' }} />
              <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                Паттерны
              </h3>
            </div>

            <ul className="space-y-3">
              {summary.patterns.map((pattern, index) => (
                <li
                  key={index}
                  className="flex items-start gap-2 text-sm"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  <span style={{ color: 'var(--accent)' }}>•</span>
                  {pattern}
                </li>
              ))}
            </ul>
          </Card>
        )}

        {/* Food-sleep connection */}
        {summary?.food_sleep_connection && (
          <Card>
            <div
              className="flex items-start gap-3 p-3 rounded-xl"
              style={{ background: 'var(--accent-soft)' }}
            >
              <Lightbulb className="w-5 h-5 flex-shrink-0" style={{ color: 'var(--accent)' }} />
              <div>
                <p className="text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                  Связь сна и питания
                </p>
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                  {summary.food_sleep_connection}
                </p>
              </div>
            </div>
          </Card>
        )}
      </div>
    </Layout>
  );
}

export default WeeklySummary;
