// Add Food page - photo or text input

import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Layout, Card, Button } from '../components/Layout';
import { useTelegram } from '../hooks/useTelegram';
import { api } from '../api/client';
import { Camera, Type, X, Check, ArrowLeft } from 'lucide-react';

type InputMode = 'choice' | 'photo' | 'text';

export function AddFood() {
  const navigate = useNavigate();
  const { haptic } = useTelegram();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [mode, setMode] = useState<InputMode>('choice');
  const [text, setText] = useState('');
  const [photo, setPhoto] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Back button
  const handleBack = () => {
    if (mode === 'choice') {
      navigate(-1);
    } else {
      setMode('choice');
      setText('');
      setPhoto(null);
      setPhotoPreview(null);
      setError(null);
    }
  };

  // Photo selection
  const handlePhotoSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setPhoto(file);
    setPhotoPreview(URL.createObjectURL(file));
    setMode('photo');
    haptic('light');
  };

  // Submit food entry
  const handleSubmit = async () => {
    setIsLoading(true);
    setError(null);
    haptic('medium');

    try {
      if (mode === 'photo' && photo) {
        await api.addFoodPhoto(photo);
      } else if (mode === 'text' && text.trim()) {
        await api.addFoodText(text.trim());
      } else {
        setError('Добавьте фото или описание');
        setIsLoading(false);
        return;
      }

      haptic('success');
      navigate('/');
    } catch (err) {
      console.error('Failed to add food:', err);
      setError('Не удалось сохранить');
      haptic('error');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Layout>
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={handleBack}
          className="p-2 rounded-xl transition-colors"
          style={{ background: 'var(--bg-glass)' }}
        >
          <ArrowLeft className="w-5 h-5" style={{ color: 'var(--text-primary)' }} />
        </button>
        <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
          Добавить еду
        </h1>
      </div>

      {/* Choice mode */}
      {mode === 'choice' && (
        <div className="space-y-4 animate-in">
          <Card
            className="cursor-pointer"
            onClick={() => {
              haptic('light');
              fileInputRef.current?.click();
            }}
          >
            <div className="flex items-center gap-4 py-4">
              <div
                className="w-14 h-14 rounded-2xl flex items-center justify-center"
                style={{ background: 'var(--accent-soft)' }}
              >
                <Camera className="w-7 h-7" style={{ color: 'var(--accent)' }} />
              </div>
              <div>
                <h3 className="font-semibold text-lg" style={{ color: 'var(--text-primary)' }}>
                  Сделать фото
                </h3>
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                  AI распознает продукты
                </p>
              </div>
            </div>
          </Card>

          <Card
            className="cursor-pointer"
            onClick={() => {
              haptic('light');
              setMode('text');
            }}
          >
            <div className="flex items-center gap-4 py-4">
              <div
                className="w-14 h-14 rounded-2xl flex items-center justify-center"
                style={{ background: 'var(--success-soft)' }}
              >
                <Type className="w-7 h-7" style={{ color: 'var(--success)' }} />
              </div>
              <div>
                <h3 className="font-semibold text-lg" style={{ color: 'var(--text-primary)' }}>
                  Описать текстом
                </h3>
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                  Например: «салат с курицей»
                </p>
              </div>
            </div>
          </Card>

          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            capture="environment"
            onChange={handlePhotoSelect}
            className="hidden"
          />
        </div>
      )}

      {/* Photo mode */}
      {mode === 'photo' && (
        <div className="animate-in">
          {photoPreview && (
            <div className="relative mb-6">
              <img
                src={photoPreview}
                alt="Food preview"
                className="w-full rounded-2xl object-cover max-h-80"
              />
              <button
                onClick={() => {
                  setPhoto(null);
                  setPhotoPreview(null);
                  setMode('choice');
                }}
                className="absolute top-3 right-3 p-2 rounded-full"
                style={{ background: 'var(--bg-glass)' }}
              >
                <X className="w-5 h-5" style={{ color: 'var(--text-primary)' }} />
              </button>
            </div>
          )}

          {error && (
            <div
              className="p-3 rounded-xl mb-4 text-sm"
              style={{ background: 'var(--error-soft)', color: 'var(--error)' }}
            >
              {error}
            </div>
          )}

          <Button onClick={handleSubmit} loading={isLoading} className="w-full">
            <Check className="w-5 h-5 mr-2" />
            Сохранить
          </Button>
        </div>
      )}

      {/* Text mode */}
      {mode === 'text' && (
        <div className="animate-in">
          <div className="mb-6">
            <label
              className="block text-sm font-medium mb-2"
              style={{ color: 'var(--text-secondary)' }}
            >
              Что ты съел?
            </label>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Например: овсянка с ягодами и мёдом"
              className="input-field min-h-[120px] resize-none"
              autoFocus
            />
            <p className="text-xs mt-2" style={{ color: 'var(--text-tertiary)' }}>
              Опиши еду своими словами, без граммов и калорий
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
            disabled={!text.trim()}
            className="w-full"
          >
            <Check className="w-5 h-5 mr-2" />
            Сохранить
          </Button>
        </div>
      )}
    </Layout>
  );
}

export default AddFood;
