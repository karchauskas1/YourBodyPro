// Dashboard - main screen

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { format } from 'date-fns';
import { ru } from 'date-fns/locale';
import { Layout, PageHeader, Card, Button, LoadingSpinner, EmptyState } from '../components/Layout';
import { useStore } from '../store/useStore';
import { useTelegram } from '../hooks/useTelegram';
import { api } from '../api/client';
import type { DashboardData, FoodEntry, WorkoutEntry } from '../types';
import {
  Utensils,
  Moon,
  Plus,
  ChevronRight,
  BarChart3,
  Settings,
  Sparkles,
  Calendar,
  Dumbbell
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
  const [workouts, setWorkouts] = useState<WorkoutEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

      // Load today's workouts
      const today = new Date().toISOString().split('T')[0];
      try {
        const workoutsData = await api.getWorkoutsByDate(today);
        setWorkouts(workoutsData.workouts || []);
      } catch {
        // Silently fail if workouts can't be loaded
        setWorkouts([]);
      }
    } catch (err) {
      console.error('Failed to load dashboard:', err);
      setError('Не удалось загрузить данные');
    } finally {
      setIsLoading(false);
    }
  };

  const handleFoodEntryClick = (entry: FoodEntry) => {
    haptic('light');
    navigate(`/food/${entry.id}`);
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

        {/* Workout Tracker Card */}
        <Card className="animate-in">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Dumbbell className="w-5 h-5" style={{ color: 'var(--accent)' }} />
              <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                Тренировки
              </h3>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                haptic('light');
                navigate('/workout/add');
              }}
              className="whitespace-nowrap flex items-center gap-1"
            >
              <Plus className="w-4 h-4 flex-shrink-0" />
              Добавить
            </Button>
          </div>

          {workouts.length > 0 ? (
            <div className="space-y-2">
              {workouts.map((workout) => {
                const intensityLabels = ['😌 Легкая', '🙂 Легкая+', '😊 Средняя', '💪 Интенсивная', '🔥 Очень интенсивная'];
                return (
                  <div
                    key={workout.id}
                    className="flex items-center gap-3 p-3 rounded-xl"
                    style={{ background: 'var(--bg-secondary)' }}
                  >
                    <div
                      className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
                      style={{ background: 'var(--accent-soft)' }}
                    >
                      <Dumbbell className="w-5 h-5" style={{ color: 'var(--accent)' }} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-medium truncate" style={{ color: 'var(--text-primary)' }}>
                        {workout.workout_name}
                      </div>
                      <div className="text-sm flex items-center gap-2" style={{ color: 'var(--text-tertiary)' }}>
                        <span>{workout.duration_minutes} мин</span>
                        <span>•</span>
                        <span>{intensityLabels[workout.intensity - 1]}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div
              className="py-6 text-center rounded-xl"
              style={{ background: 'var(--bg-secondary)' }}
            >
              <Dumbbell
                className="w-8 h-8 mx-auto mb-2"
                style={{ color: 'var(--text-tertiary)' }}
              />
              <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                Нет тренировок сегодня
              </p>
            </div>
          )}
        </Card>

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

    </Layout>
  );
}

export default Dashboard;
