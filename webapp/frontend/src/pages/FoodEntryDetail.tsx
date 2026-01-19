// Food Entry Detail page - view and edit food entry

import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Layout, PageHeader, Card, Button, LoadingSpinner } from '../components/Layout';
import { useTelegram } from '../hooks/useTelegram';
import { api } from '../api/client';
import type { FoodEntry } from '../types';
import { Utensils, Trash2, Edit3, ArrowLeft } from 'lucide-react';

export function FoodEntryDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { haptic, showConfirm } = useTelegram();
  const [entry, setEntry] = useState<FoodEntry | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [editedDescription, setEditedDescription] = useState('');
  const [hungerBefore, setHungerBefore] = useState<number | undefined>(undefined);
  const [fullnessAfter, setFullnessAfter] = useState<number | undefined>(undefined);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    loadEntry();
  }, [id]);

  const loadEntry = async () => {
    if (!id) return;

    try {
      setIsLoading(true);
      // Получаем записи за сегодня и находим нужную
      const response = await api.getTodayFood();
      const foundEntry = response.entries.find(e => e.id === parseInt(id));

      if (foundEntry) {
        setEntry(foundEntry);
        setEditedDescription(foundEntry.description);
        setHungerBefore(foundEntry.hunger_before);
        setFullnessAfter(foundEntry.fullness_after);
      } else {
        // Если не нашли в сегодняшних, попробуем получить из календаря
        navigate('/');
      }
    } catch (err) {
      console.error('Failed to load entry:', err);
      haptic('error');
      navigate('/');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async () => {
    if (!entry || !editedDescription.trim()) return;

    setIsSaving(true);
    haptic('medium');

    try {
      // Обновляем описание
      await api.updateFoodEntry(entry.id, editedDescription.trim());

      // Обновляем оценки голода/сытости
      if (hungerBefore !== entry.hunger_before || fullnessAfter !== entry.fullness_after) {
        await api.updateFoodEntryFeelings(entry.id, hungerBefore, fullnessAfter);
      }

      haptic('success');
      navigate('/');
    } catch (err) {
      console.error('Failed to save entry:', err);
      haptic('error');
    } finally {
      setIsSaving(false);
      setIsEditing(false);
    }
  };

  const handleDelete = async () => {
    if (!entry) return;

    const confirmed = await showConfirm('Удалить этот прием пищи?');
    if (!confirmed) return;

    setIsDeleting(true);
    haptic('medium');

    try {
      await api.deleteFoodEntry(entry.id);
      haptic('success');
      navigate('/');
    } catch (err) {
      console.error('Failed to delete entry:', err);
      haptic('error');
      setIsDeleting(false);
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

  if (!entry) {
    return null;
  }

  return (
    <Layout>
      <PageHeader
        title="Прием пищи"
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
        {/* Main card */}
        <Card>
          <div className="flex items-start gap-3 mb-4">
            <div
              className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0"
              style={{ background: 'var(--accent-soft)' }}
            >
              <Utensils className="w-6 h-6" style={{ color: 'var(--accent)' }} />
            </div>
            <div className="flex-1">
              <div className="text-sm mb-1" style={{ color: 'var(--text-secondary)' }}>
                {entry.time}
              </div>
              {isEditing ? (
                <textarea
                  value={editedDescription}
                  onChange={(e) => setEditedDescription(e.target.value)}
                  className="w-full input-field resize-none"
                  rows={3}
                  placeholder="Описание приема пищи"
                  autoFocus
                />
              ) : (
                <p className="text-base font-medium" style={{ color: 'var(--text-primary)' }}>
                  {entry.description}
                </p>
              )}
            </div>
          </div>

          {/* Edit button */}
          {!isEditing && (
            <button
              onClick={() => {
                haptic('light');
                setIsEditing(true);
              }}
              className="w-full py-2 px-4 rounded-xl flex items-center justify-center gap-2 transition-colors mb-3"
              style={{ background: 'var(--bg-secondary)', color: 'var(--accent)' }}
            >
              <Edit3 className="w-4 h-4" />
              Редактировать описание
            </button>
          )}

          {/* Photo indicator */}
          {entry.photo_file_id && (
            <div
              className="py-2 px-3 rounded-lg text-sm mb-3"
              style={{ background: 'var(--bg-secondary)', color: 'var(--text-secondary)' }}
            >
              📷 Добавлено с фото
            </div>
          )}

          {/* Source indicator */}
          <div
            className="py-2 px-3 rounded-lg text-sm"
            style={{ background: 'var(--bg-secondary)', color: 'var(--text-secondary)' }}
          >
            {entry.source === 'telegram' ? '💬 Добавлено через бота' : '📱 Добавлено через приложение'}
          </div>
        </Card>

        {/* Hunger before */}
        <Card>
          <h3 className="font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>
            Голод перед едой
          </h3>
          <div className="flex gap-2">
            {[1, 2, 3, 4, 5].map((level) => (
              <button
                key={level}
                onClick={() => {
                  if (isEditing) {
                    haptic('selection');
                    setHungerBefore(hungerBefore === level ? undefined : level);
                  }
                }}
                disabled={!isEditing}
                className="flex-1 py-3 px-2 rounded-xl text-sm font-medium transition-all"
                style={{
                  background: hungerBefore === level ? 'var(--accent)' : 'var(--bg-secondary)',
                  color: hungerBefore === level ? 'white' : 'var(--text-primary)',
                  opacity: isEditing ? 1 : 0.7,
                  cursor: isEditing ? 'pointer' : 'default',
                }}
              >
                {level === 1 && '😐'}
                {level === 2 && '🙂'}
                {level === 3 && '😊'}
                {level === 4 && '😋'}
                {level === 5 && '🤤'}
                <div className="text-xs mt-1">{level}</div>
              </button>
            ))}
          </div>
          <p className="text-xs mt-2" style={{ color: 'var(--text-tertiary)' }}>
            1 - совсем не голоден, 5 - очень голоден
          </p>
        </Card>

        {/* Fullness after */}
        <Card>
          <h3 className="font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
            Сытость после еды
          </h3>
          <p className="text-xs mb-3" style={{ color: 'var(--text-tertiary)' }}>
            💡 Отметь сытость через 10-15 минут после еды, когда почувствуешь полное насыщение
          </p>
          <div className="flex gap-2">
            {[1, 2, 3, 4, 5].map((level) => (
              <button
                key={level}
                onClick={() => {
                  if (isEditing) {
                    haptic('selection');
                    setFullnessAfter(fullnessAfter === level ? undefined : level);
                  }
                }}
                disabled={!isEditing}
                className="flex-1 py-3 px-2 rounded-xl text-sm font-medium transition-all"
                style={{
                  background: fullnessAfter === level ? 'var(--success)' : 'var(--bg-secondary)',
                  color: fullnessAfter === level ? 'white' : 'var(--text-primary)',
                  opacity: isEditing ? 1 : 0.7,
                  cursor: isEditing ? 'pointer' : 'default',
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
        </Card>

        {/* Actions */}
        {isEditing ? (
          <div className="flex gap-3">
            <button
              onClick={() => {
                haptic('light');
                setIsEditing(false);
                setEditedDescription(entry.description);
                setHungerBefore(entry.hunger_before);
                setFullnessAfter(entry.fullness_after);
              }}
              className="flex-1 py-3 rounded-xl font-medium"
              style={{ background: 'var(--bg-secondary)', color: 'var(--text-primary)' }}
            >
              Отмена
            </button>
            <Button
              onClick={handleSave}
              disabled={!editedDescription.trim() || isSaving}
              className="flex-1"
            >
              {isSaving ? 'Сохранение...' : 'Сохранить'}
            </Button>
          </div>
        ) : (
          <button
            onClick={handleDelete}
            disabled={isDeleting}
            className="w-full py-3 rounded-xl font-medium flex items-center justify-center gap-2 transition-colors"
            style={{
              background: 'var(--error-soft)',
              color: 'var(--error)',
              opacity: isDeleting ? 0.5 : 1,
            }}
          >
            <Trash2 className="w-4 h-4" />
            {isDeleting ? 'Удаление...' : 'Удалить прием пищи'}
          </button>
        )}
      </div>
    </Layout>
  );
}

export default FoodEntryDetail;

