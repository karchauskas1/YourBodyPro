// Daily Summary page - evening analysis

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { format } from 'date-fns';
import { ru } from 'date-fns/locale';
import { Layout, Card, Button, LoadingSpinner, EmptyState } from '../components/Layout';
import { api } from '../api/client';
import type { DailySummary as DailySummaryType } from '../types';
import { ArrowLeft, Sparkles, Utensils, MessageCircle, Lightbulb } from 'lucide-react';

export function DailySummary() {
  const navigate = useNavigate();
  const [summary, setSummary] = useState<DailySummaryType | null>(null);
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

      const response = await api.getTodaySummary();

      if (!response.summary) {
        setNoData(true);
      } else {
        setSummary(response.summary);
      }
    } catch (err) {
      console.error('Failed to load summary:', err);
      setError('Не удалось загрузить итог');
    } finally {
      setIsLoading(false);
    }
  };

  const today = new Date();
  const dateStr = format(today, 'd MMMM', { locale: ru });

  if (isLoading) {
    return (
      <Layout>
        <div className="flex flex-col items-center justify-center min-h-[60vh]">
          <LoadingSpinner size="lg" />
          <p className="mt-4 text-sm" style={{ color: 'var(--text-secondary)' }}>
            Анализируем рацион...
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
            Итог дня
          </h1>
        </div>

        <EmptyState
          icon={<Utensils className="w-12 h-12" />}
          title="Нет данных"
          description="Добавь еду в течение дня, чтобы получить вечерний анализ"
          action={
            <Button onClick={() => navigate('/food/add')}>
              Добавить еду
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
            Итог дня
          </h1>
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
            {dateStr}
          </p>
        </div>
      </div>

      <div className="space-y-4 animate-in">
        {/* Foods list */}
        {summary?.foods_list && summary.foods_list.length > 0 && (
          <Card>
            <div className="flex items-center gap-2 mb-3">
              <Utensils className="w-5 h-5" style={{ color: 'var(--accent)' }} />
              <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                Что ты съел сегодня
              </h3>
            </div>
            <ul className="space-y-2">
              {summary.foods_list.map((food, index) => (
                <li
                  key={index}
                  className="flex items-start gap-2 text-sm"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  <span style={{ color: 'var(--accent)' }}>•</span>
                  {food}
                </li>
              ))}
            </ul>
          </Card>
        )}

        {/* Analysis */}
        {summary?.analysis && (
          <Card>
            <div className="flex items-center gap-2 mb-3">
              <MessageCircle className="w-5 h-5" style={{ color: 'var(--accent)' }} />
              <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                Анализ
              </h3>
            </div>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              {summary.analysis}
            </p>
          </Card>
        )}

        {/* Balance note */}
        {summary?.balance_note && (
          <Card>
            <div
              className="flex items-start gap-3 p-3 rounded-xl"
              style={{ background: 'var(--accent-soft)' }}
            >
              <Sparkles className="w-5 h-5 flex-shrink-0" style={{ color: 'var(--accent)' }} />
              <p className="text-sm" style={{ color: 'var(--text-primary)' }}>
                {summary.balance_note}
              </p>
            </div>
          </Card>
        )}

        {/* Suggestion */}
        {summary?.suggestion && (
          <Card>
            <div
              className="flex items-start gap-3 p-3 rounded-xl"
              style={{ background: 'var(--success-soft)' }}
            >
              <Lightbulb className="w-5 h-5 flex-shrink-0" style={{ color: 'var(--success)' }} />
              <p className="text-sm" style={{ color: 'var(--text-primary)' }}>
                {summary.suggestion}
              </p>
            </div>
          </Card>
        )}
      </div>
    </Layout>
  );
}

export default DailySummary;
