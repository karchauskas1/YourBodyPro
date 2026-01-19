// Food List page - shows all food entries for today

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Layout, PageHeader, Card, LoadingSpinner, EmptyState } from '../components/Layout';
import { useTelegram } from '../hooks/useTelegram';
import { api } from '../api/client';
import type { FoodEntry } from '../types';
import { Utensils, Plus, ArrowLeft } from 'lucide-react';

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
          {entry.photo_file_id && (
            <span className="text-xs" title="С фото">
              📷
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

export function FoodList() {
  const navigate = useNavigate();
  const { haptic } = useTelegram();
  const [entries, setEntries] = useState<FoodEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadEntries();
  }, []);

  const loadEntries = async () => {
    try {
      setIsLoading(true);
      const response = await api.getTodayFood();
      setEntries(response.entries);
    } catch (err) {
      console.error('Failed to load food entries:', err);
      haptic('error');
    } finally {
      setIsLoading(false);
    }
  };

  const handleEntryClick = (entry: FoodEntry) => {
    haptic('light');
    navigate(`/food/${entry.id}`);
  };

  if (isLoading) {
    return (
      <Layout>
        <PageHeader
          title="Питание сегодня"
          action={
            <button
              onClick={() => {
                haptic('light');
                navigate('/');
              }}
              className="p-2 rounded-xl transition-colors"
              style={{ background: 'var(--bg-glass)' }}
            >
              <ArrowLeft className="w-5 h-5" style={{ color: 'var(--text-secondary)' }} />
            </button>
          }
        />
        <div className="flex items-center justify-center min-h-[60vh]">
          <LoadingSpinner size="lg" />
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <PageHeader
        title="Питание сегодня"
        action={
          <button
            onClick={() => {
              haptic('light');
              navigate('/');
            }}
            className="p-2 rounded-xl transition-colors"
            style={{ background: 'var(--bg-glass)' }}
          >
            <ArrowLeft className="w-5 h-5" style={{ color: 'var(--text-secondary)' }} />
          </button>
        }
      />

      <div className="space-y-4">
        {entries.length > 0 ? (
          <>
            <Card>
              <div className="space-y-2">
                {entries.map((entry) => (
                  <FoodItem key={entry.id} entry={entry} onClick={() => handleEntryClick(entry)} />
                ))}
              </div>
            </Card>

            <div className="text-center text-sm" style={{ color: 'var(--text-tertiary)' }}>
              Всего приемов пищи: {entries.length}
            </div>
          </>
        ) : (
          <EmptyState
            icon={<Utensils className="w-12 h-12" />}
            title="Нет записей"
            description="Вы еще не добавили ни одного приема пищи"
            action={
              <button
                onClick={() => {
                  haptic('light');
                  navigate('/food/add');
                }}
                className="btn-primary flex items-center gap-2"
              >
                <Plus className="w-5 h-5" />
                Добавить прием пищи
              </button>
            }
          />
        )}
      </div>
    </Layout>
  );
}

export default FoodList;
