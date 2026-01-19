// Dashboard - main screen

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { format } from 'date-fns';
import { ru } from 'date-fns/locale';
import { Layout, PageHeader, Card, Button, LoadingSpinner, EmptyState } from '../components/Layout';
import { useStore } from '../store/useStore';
import { useTelegram } from '../hooks/useTelegram';
import { api } from '../api/client';
import type { DashboardData, FoodEntry } from '../types';
import {
  Utensils,
  Moon,
  Plus,
  ChevronRight,
  BarChart3,
  Settings,
  Sparkles,
  Calendar
} from 'lucide-react';

// Food entry item
function FoodItem({ entry, onClick }: { entry: FoodEntry; onClick: () => void }) {
  return (
    <div className="food-entry slide-up cursor-pointer" onClick={onClick}>
      <div
        className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
        style={{ background: 'var(--accent-soft)' }}
      >
        <Utensils className="w-5 h-5" style={{ color: 'var(--accent)' }} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-medium truncate" style={{ color: 'var(--text-primary)' }}>
          {entry.description}
        </div>
        <div className="text-sm flex items-center gap-2" style={{ color: 'var(--text-tertiary)' }}>
          <span>{entry.time}</span>
          {entry.hunger_before && (
            <span className="text-xs" title="Голод перед едой">
              🍽️ {entry.hunger_before}
            </span>
          )}
          {entry.fullness_after && (
            <span className="text-xs" title="Сытость после еды">
              ✅ {entry.fullness_after}
            </span>
          )}
        </div>
      </div>
      {!entry.fullness_after && (
        <div
          className="text-xs px-2 py-1 rounded-lg"
          style={{ background: 'var(--warning-soft)', color: 'var(--warning)' }}
        >
          Отметить сытость
        </div>
      )}
    </div>
  );
}

// Sleep score display
function SleepScore({ score }: { score: number | null }) {
  if (score === null) {
    return (
      <div className="text-sm" style={{ color: 'var(--text-tertiary)' }}>
        Не указано
      </div>
    );
  }

  const colors = [
    'var(--error)',
    'var(--warning)',
    'var(--warning)',
    'var(--success)',
    'var(--success)',
  ];

  return (
    <div className="flex items-center gap-1">
      {[1, 2, 3, 4, 5].map((i) => (
        <div
          key={i}
          className="w-3 h-3 rounded-full transition-all"
          style={{
            background: i <= score ? colors[score - 1] : 'var(--border)',
          }}
        />
      ))}
      <span className="ml-2 font-medium" style={{ color: 'var(--text-primary)' }}>
        {score}/5
      </span>
    </div>
  );
}

export function Dashboard() {
  const navigate = useNavigate();
  const { haptic } = useTelegram();
  const { profile, setDashboard } = useStore();
  const [data, setData] = useState<DashboardData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedEntry, setSelectedEntry] = useState<FoodEntry | null>(null);
  const [fullnessRating, setFullnessRating] = useState<number | undefined>(undefined);
  const [isUpdating, setIsUpdating] = useState(false);

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const dashboardData = await api.getDashboard();
      setData(dashboardData);
      setDashboard(dashboardData);
    } catch (err) {
      console.error('Failed to load dashboard:', err);
      setError('Не удалось загрузить данные');
    } finally {
      setIsLoading(false);
    }
  };

  const handleFoodEntryClick = (entry: FoodEntry) => {
    haptic('light');
    setSelectedEntry(entry);
    setFullnessRating(entry.fullness_after);
  };

  const handleUpdateFullness = async () => {
    if (!selectedEntry || fullnessRating === undefined) return;

    setIsUpdating(true);
    haptic('medium');

    try {
      await api.updateFoodEntryFeelings(selectedEntry.id, undefined, fullnessRating);

      // Обновляем локальные данные
      if (data) {
        const updatedEntries = data.food.entries.map((entry) =>
          entry.id === selectedEntry.id
            ? { ...entry, fullness_after: fullnessRating }
            : entry
        );
        setData({
          ...data,
          food: { ...data.food, entries: updatedEntries },
        });
      }

      haptic('success');
      setSelectedEntry(null);
      setFullnessRating(undefined);
    } catch (err) {
      console.error('Failed to update fullness:', err);
      haptic('error');
    } finally {
      setIsUpdating(false);
    }
  };

  if (isLoading) {
    return (
      <Layout>
        <div className="flex items-center justify-center min-h-[60vh]">
          <LoadingSpinner size="lg" />
        </div>
      </Layout>
    );
  }

  if (error) {
    return (
      <Layout>
        <EmptyState
          title="Ошибка загрузки"
          description={error}
          action={
            <Button onClick={loadDashboard} variant="secondary">
              Попробовать снова
            </Button>
          }
        />
      </Layout>
    );
  }

  const today = new Date();
  const dateStr = format(today, 'd MMMM', { locale: ru });

  return (
    <Layout>
      <PageHeader
        title={`Сегодня, ${dateStr}`}
        action={
          <button
            onClick={() => {
              haptic('light');
              navigate('/settings');
            }}
            className="p-2 rounded-xl transition-colors"
            style={{ background: 'var(--bg-glass)' }}
          >
            <Settings className="w-5 h-5" style={{ color: 'var(--text-secondary)' }} />
          </button>
        }
      />

      <div className="space-y-4">
        {/* Food Tracker Card */}
        {profile?.food_tracker_enabled && (
          <Card className="animate-in">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Utensils className="w-5 h-5" style={{ color: 'var(--accent)' }} />
                <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                  Питание сегодня
                </h3>
              </div>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  haptic('light');
                  navigate('/food/add');
                }}
                className="whitespace-nowrap flex items-center gap-1"
              >
                <Plus className="w-4 h-4 flex-shrink-0" />
                Добавить
              </Button>
            </div>

            {data?.food.entries && data.food.entries.length > 0 ? (
              <div className="space-y-2">
                {data.food.entries.slice(0, 3).map((entry) => (
                  <FoodItem key={entry.id} entry={entry} onClick={() => handleFoodEntryClick(entry)} />
                ))}
                {data.food.entries.length > 3 && (
                  <button
                    onClick={() => {
                      haptic('light');
                      navigate('/food');
                    }}
                    className="w-full py-2 text-sm font-medium transition-colors"
                    style={{ color: 'var(--accent)' }}
                  >
                    Показать все ({data.food.entries.length})
                  </button>
                )}
              </div>
            ) : (
              <div
                className="py-8 text-center rounded-xl"
                style={{ background: 'var(--bg-secondary)' }}
              >
                <Utensils
                  className="w-8 h-8 mx-auto mb-2"
                  style={{ color: 'var(--text-tertiary)' }}
                />
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                  Пока ничего не добавлено
                </p>
              </div>
            )}
          </Card>
        )}

        {/* Sleep Tracker Card */}
        {profile?.sleep_tracker_enabled && (
          <Card
            className="animate-in"
            onClick={() => {
              if (!data?.sleep.score) {
                haptic('light');
                navigate('/sleep');
              }
            }}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center"
                  style={{ background: 'var(--accent-soft)' }}
                >
                  <Moon className="w-5 h-5" style={{ color: 'var(--accent)' }} />
                </div>
                <div>
                  <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                    Сон
                  </h3>
                  <SleepScore score={data?.sleep.score ?? null} />
                </div>
              </div>
              {!data?.sleep.score && (
                <ChevronRight className="w-5 h-5" style={{ color: 'var(--text-tertiary)' }} />
              )}
            </div>
          </Card>
        )}

        {/* Daily Summary Card */}
        {profile?.food_tracker_enabled && (
          <Card
            className="animate-in"
            onClick={() => {
              haptic('light');
              navigate('/summary');
            }}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center"
                  style={{
                    background: data?.summary.available
                      ? 'var(--success-soft)'
                      : 'var(--bg-secondary)',
                  }}
                >
                  <Sparkles
                    className="w-5 h-5"
                    style={{
                      color: data?.summary.available
                        ? 'var(--success)'
                        : 'var(--text-tertiary)',
                    }}
                  />
                </div>
                <div>
                  <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                    Вечерний итог
                  </h3>
                  <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                    {data?.summary.available
                      ? 'Готов к просмотру'
                      : `Будет доступен в ${profile.evening_summary_time}`}
                  </p>
                </div>
              </div>
              <ChevronRight className="w-5 h-5" style={{ color: 'var(--text-tertiary)' }} />
            </div>
          </Card>
        )}

        {/* Food Calendar Card */}
        {profile?.food_tracker_enabled && (
          <Card
            className="animate-in"
            onClick={() => {
              haptic('light');
              navigate('/calendar');
            }}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center"
                  style={{ background: 'var(--warning-soft)' }}
                >
                  <Calendar className="w-5 h-5" style={{ color: 'var(--warning)' }} />
                </div>
                <div>
                  <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                    Календарь питания
                  </h3>
                  <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                    История по дням
                  </p>
                </div>
              </div>
              <ChevronRight className="w-5 h-5" style={{ color: 'var(--text-tertiary)' }} />
            </div>
          </Card>
        )}

        {/* Weekly Review Card */}
        {profile?.weekly_review_enabled && (
          <Card
            className="animate-in"
            onClick={() => {
              haptic('light');
              navigate('/weekly');
            }}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center"
                  style={{ background: 'var(--accent-soft)' }}
                >
                  <BarChart3 className="w-5 h-5" style={{ color: 'var(--accent)' }} />
                </div>
                <div>
                  <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                    Недельный обзор
                  </h3>
                  <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                    Паттерны и связи
                  </p>
                </div>
              </div>
              <ChevronRight className="w-5 h-5" style={{ color: 'var(--text-tertiary)' }} />
            </div>
          </Card>
        )}

        {/* No features enabled */}
        {!profile?.food_tracker_enabled &&
          !profile?.sleep_tracker_enabled &&
          !profile?.weekly_review_enabled && (
            <EmptyState
              icon={<Settings className="w-12 h-12" />}
              title="Нет активных функций"
              description="Включите трекеры в настройках, чтобы начать"
              action={
                <Button onClick={() => navigate('/settings')}>
                  Открыть настройки
                </Button>
              }
            />
          )}

        {/* Edit request button */}
        {(profile?.food_tracker_enabled ||
          profile?.sleep_tracker_enabled ||
          profile?.weekly_review_enabled) && (
          <button
            onClick={() => {
              haptic('light');
              navigate('/edit-request');
            }}
            className="w-full py-3 text-sm font-medium rounded-xl transition-colors mt-2"
            style={{ color: 'var(--text-secondary)', background: 'var(--bg-glass)' }}
          >
            Изменить запрос
          </button>
        )}
      </div>

      {/* Fullness rating modal */}
      {selectedEntry && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 flex items-end justify-center z-50 animate-in"
          onClick={() => {
            setSelectedEntry(null);
            setFullnessRating(undefined);
          }}
        >
          <div
            className="w-full max-w-md p-6 rounded-t-3xl"
            style={{ background: 'var(--bg-primary)' }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-bold mb-2" style={{ color: 'var(--text-primary)' }}>
              {selectedEntry.description}
            </h3>
            <p className="text-sm mb-1" style={{ color: 'var(--text-secondary)' }}>
              Время: {selectedEntry.time}
            </p>
            {selectedEntry.hunger_before && (
              <p className="text-sm mb-4" style={{ color: 'var(--text-secondary)' }}>
                Голод перед едой: {selectedEntry.hunger_before}/5
              </p>
            )}

            <div className="mb-6">
              <label className="text-sm font-medium mb-3 block" style={{ color: 'var(--text-secondary)' }}>
                Насколько насытился после еды?
              </label>
              <p className="text-xs mb-3" style={{ color: 'var(--text-tertiary)' }}>
                💡 Отметь сытость через 10-15 минут после еды, когда почувствуешь полное насыщение
              </p>
              <div className="flex gap-2">
                {[1, 2, 3, 4, 5].map((level) => (
                  <button
                    key={level}
                    onClick={() => {
                      haptic('selection');
                      setFullnessRating(level);
                    }}
                    className="flex-1 py-3 px-2 rounded-xl text-sm font-medium transition-all"
                    style={{
                      background: fullnessRating === level ? 'var(--accent)' : 'var(--bg-secondary)',
                      color: fullnessRating === level ? 'white' : 'var(--text-primary)',
                    }}
                  >
                    {level === 1 && '😐'}
                    {level === 2 && '🙂'}
                    {level === 3 && '😊'}
                    {level === 4 && '😌'}
                    {level === 5 && '🤤'}
                    <div className="text-xs mt-1">{level}</div>
                  </button>
                ))}
              </div>
              <p className="text-xs mt-2" style={{ color: 'var(--text-tertiary)' }}>
                1 - совсем не насытился, 5 - очень сыт
              </p>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => {
                  setSelectedEntry(null);
                  setFullnessRating(undefined);
                }}
                className="flex-1 py-3 rounded-xl font-medium"
                style={{ background: 'var(--bg-secondary)', color: 'var(--text-primary)' }}
              >
                Отмена
              </button>
              <button
                onClick={handleUpdateFullness}
                disabled={fullnessRating === undefined || isUpdating}
                className="flex-1 py-3 rounded-xl font-medium"
                style={{
                  background: fullnessRating === undefined ? 'var(--bg-secondary)' : 'var(--accent)',
                  color: fullnessRating === undefined ? 'var(--text-tertiary)' : 'white',
                  opacity: isUpdating ? 0.5 : 1,
                }}
              >
                {isUpdating ? 'Сохранение...' : 'Сохранить'}
              </button>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}

export default Dashboard;
