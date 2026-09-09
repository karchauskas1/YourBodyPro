// Add Food page - photo or text input

import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Layout, Card, Button } from '../components/Layout';
import { useTelegram } from '../hooks/useTelegram';
import { api } from '../api/client';
import { useStore } from '../store/useStore';
import { Camera, Type, X, Check, ArrowLeft, ImageIcon, Clock } from 'lucide-react';

type InputMode = 'choice' | 'photo' | 'text';

export function AddFood() {
  const navigate = useNavigate();
  const { haptic } = useTelegram();
  const { profile } = useStore();
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const galleryInputRef = useRef<HTMLInputElement>(null);

  // Округляем вниз, чтобы запись не попадала в будущее или предыдущий час.
  const getCurrentTime = () => {
    const now = new Date();
    const hours = now.getHours();
    const minutes = Math.floor(now.getMinutes() / 15) * 15;
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
  };

  const [mode, setMode] = useState<InputMode>('choice');
  const [text, setText] = useState('');
  const [photo, setPhoto] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const [photoDescription, setPhotoDescription] = useState(''); // Описание к фото для нейронки
  const [selectedTime, setSelectedTime] = useState(getCurrentTime());
  const [hungerBefore, setHungerBefore] = useState<number | undefined>(undefined);
  const [fullnessAfter, setFullnessAfter] = useState<number | undefined>(undefined);
  const [ateWithoutGadgets, setAteWithoutGadgets] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Get text based on gender
  const getGenderText = () => {
    if (profile?.gender === 'male') {
      return 'Я ел без гаджетов';
    } else if (profile?.gender === 'female') {
      return 'Я ела без гаджетов';
    }
    return 'Я ел/ела без гаджетов';
  };

  // Back button
  const handleBack = () => {
    if (mode === 'choice') {
      navigate(-1);
    } else {
      setMode('choice');
      setText('');
      setPhoto(null);
      setPhotoPreview(null);
      setPhotoDescription('');
      setError(null);
    }
  };

  // Photo selection
  // Compress image before upload
  const compressImage = async (file: File): Promise<File> => {
    return new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const img = new Image();
        img.onload = () => {
          const canvas = document.createElement('canvas');
          const ctx = canvas.getContext('2d')!;

          // Calculate new dimensions (max 1920px on longest side)
          let width = img.width;
          let height = img.height;
          const maxSize = 1920;

          if (width > height && width > maxSize) {
            height = (height / width) * maxSize;
            width = maxSize;
          } else if (height > maxSize) {
            width = (width / height) * maxSize;
            height = maxSize;
          }

          canvas.width = width;
          canvas.height = height;

          // Draw and compress
          ctx.drawImage(img, 0, 0, width, height);
          canvas.toBlob(
            (blob) => {
              if (blob) {
                const compressedFile = new File([blob], file.name, {
                  type: 'image/jpeg',
                  lastModified: Date.now(),
                });
                console.log('🗜️ Image compressed:', {
                  original: `${(file.size / 1024 / 1024).toFixed(2)} MB`,
                  compressed: `${(compressedFile.size / 1024 / 1024).toFixed(2)} MB`,
                  reduction: `${(((file.size - compressedFile.size) / file.size) * 100).toFixed(1)}%`
                });
                resolve(compressedFile);
              } else {
                resolve(file);
              }
            },
            'image/jpeg',
            0.85 // 85% quality
          );
        };
        img.src = e.target?.result as string;
      };
      reader.readAsDataURL(file);
    });
  };

  const handlePhotoSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    console.log('📷 Original file:', {
      name: file.name,
      size: `${(file.size / 1024 / 1024).toFixed(2)} MB`,
      type: file.type
    });

    // Compress image
    const compressedFile = await compressImage(file);

    setPhoto(compressedFile);
    setPhotoPreview(URL.createObjectURL(compressedFile));
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
        console.log('🔄 Starting photo upload:', {
          name: photo.name,
          size: `${(photo.size / 1024 / 1024).toFixed(2)} MB`,
          type: photo.type,
          time: selectedTime,
          hungerBefore,
          fullnessAfter,
          description: photoDescription
        });
        const result = await api.addFoodPhoto(
          photo,
          selectedTime,
          hungerBefore,
          fullnessAfter,
          photoDescription.trim() || undefined,
          ateWithoutGadgets
        );
        console.log('✅ Photo uploaded successfully:', result);
      } else if (mode === 'text' && text.trim()) {
        await api.addFoodText(text.trim(), selectedTime, hungerBefore, fullnessAfter, ateWithoutGadgets);
      } else {
        setError('Добавьте фото или описание');
        setIsLoading(false);
        return;
      }

      haptic('success');
      navigate('/');
    } catch (err: any) {
      console.error('❌ Failed to add food:', {
        error: err,
        message: err?.message,
        detail: err?.detail,
        status: err?.status
      });

      // Более детальное сообщение об ошибке
      let errorMessage = 'Не удалось сохранить';
      if (err?.status === 413 || err?.message?.includes('too large')) {
        errorMessage = 'Фото слишком большое. Максимум 10MB';
      } else if (err?.status === 500) {
        errorMessage = 'Ошибка сервера. Попробуйте позже';
      } else if (err?.message) {
        errorMessage = err.message;
      } else if (err?.detail) {
        errorMessage = err.detail;
      }

      setError(errorMessage);
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
          {/* Camera */}
          <Card
            className="cursor-pointer"
            onClick={() => {
              haptic('light');
              cameraInputRef.current?.click();
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

          {/* Gallery */}
          <Card
            className="cursor-pointer"
            onClick={() => {
              haptic('light');
              galleryInputRef.current?.click();
            }}
          >
            <div className="flex items-center gap-4 py-4">
              <div
                className="w-14 h-14 rounded-2xl flex items-center justify-center"
                style={{ background: 'var(--warning-soft)' }}
              >
                <ImageIcon className="w-7 h-7" style={{ color: 'var(--warning)' }} />
              </div>
              <div>
                <h3 className="font-semibold text-lg" style={{ color: 'var(--text-primary)' }}>
                  Выбрать из галереи
                </h3>
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                  Загрузить существующее фото
                </p>
              </div>
            </div>
          </Card>

          {/* Text */}
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

          {/* Hidden inputs */}
          <input
            ref={cameraInputRef}
            type="file"
            accept="image/*"
            capture="environment"
            onChange={handlePhotoSelect}
            className="hidden"
          />
          <input
            ref={galleryInputRef}
            type="file"
            accept="image/*"
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

          {/* Photo description */}
          <div className="mb-6">
            <label
              className="block text-sm font-medium mb-2"
              style={{ color: 'var(--text-secondary)' }}
            >
              Что на фото? (опционально)
            </label>
            <input
              type="text"
              value={photoDescription}
              onChange={(e) => setPhotoDescription(e.target.value)}
              placeholder="Например: овсяноблин с творогом"
              className="input-field"
            />
            <p className="text-xs mt-2" style={{ color: 'var(--text-tertiary)' }}>
              💡 Помоги нейронке понять, что именно ты съел
            </p>
          </div>

          {/* Time selector */}
          <div className="mb-6">
            <label
              className="flex items-center gap-2 text-sm font-medium mb-2"
              style={{ color: 'var(--text-secondary)' }}
            >
              <Clock className="w-4 h-4" />
              Время приёма пищи
            </label>
            <input
              type="time"
              value={selectedTime}
              onChange={(e) => setSelectedTime(e.target.value)}
              className="input-field"
            />
          </div>

          {/* Hunger before meal */}
          <div className="mb-6">
            <label
              className="text-sm font-medium mb-3 block"
              style={{ color: 'var(--text-secondary)' }}
            >
              Голод перед едой (опционально)
            </label>
            <div className="flex gap-2">
              {[1, 2, 3, 4, 5].map((level) => (
                <button
                  key={level}
                  onClick={() => {
                    haptic('selection');
                    setHungerBefore(hungerBefore === level ? undefined : level);
                  }}
                  className="flex-1 py-3 px-2 rounded-xl text-sm font-medium transition-all"
                  style={{
                    background:
                      hungerBefore === level ? 'var(--accent)' : 'var(--bg-secondary)',
                    color: hungerBefore === level ? 'white' : 'var(--text-primary)',
                  }}
                >
                  {level === 1 && '😐'}
                  {level === 2 && '🙂'}
                  {level === 3 && '😋'}
                  {level === 4 && '😤'}
                  {level === 5 && '🤤'}
                  <div className="text-xs mt-1">{level}</div>
                </button>
              ))}
            </div>
            <p className="text-xs mt-2" style={{ color: 'var(--text-tertiary)' }}>
              1 - очень голоден, 5 - очень сыт
            </p>
          </div>

          {/* Fullness after meal */}
          <div className="mb-6">
            <label
              className="text-sm font-medium mb-3 block"
              style={{ color: 'var(--text-secondary)' }}
            >
              Сытость после еды (опционально)
            </label>
            <div className="flex gap-2">
              {[1, 2, 3, 4, 5].map((level) => (
                <button
                  key={level}
                  onClick={() => {
                    haptic('selection');
                    setFullnessAfter(fullnessAfter === level ? undefined : level);
                  }}
                  className="flex-1 py-3 px-2 rounded-xl text-sm font-medium transition-all"
                  style={{
                    background:
                      fullnessAfter === level ? 'var(--accent)' : 'var(--bg-secondary)',
                    color: fullnessAfter === level ? 'white' : 'var(--text-primary)',
                  }}
                >
                  {level === 1 && '😐'}
                  {level === 2 && '🙂'}
                  {level === 3 && '😋'}
                  {level === 4 && '😤'}
                  {level === 5 && '🤤'}
                  <div className="text-xs mt-1">{level}</div>
                </button>
              ))}
            </div>
            <p className="text-xs mt-2" style={{ color: 'var(--text-tertiary)' }}>
              💡 Отметь сытость через 10-15 минут после еды
            </p>
            <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>
              1 - совсем не насытился, 5 - очень сыт
            </p>
          </div>

          {/* Ate without gadgets */}
          <div className="mb-6">
            <label className="flex items-center gap-3 cursor-pointer">
              <div
                className="flex items-center justify-center w-6 h-6 rounded-lg border-2 transition-all"
                style={{
                  borderColor: ateWithoutGadgets ? 'var(--accent)' : 'var(--border)',
                  background: ateWithoutGadgets ? 'var(--accent)' : 'transparent',
                }}
                onClick={() => {
                  haptic('selection');
                  setAteWithoutGadgets(!ateWithoutGadgets);
                }}
              >
                {ateWithoutGadgets && <Check className="w-4 h-4 text-white" />}
              </div>
              <span
                className="text-sm font-medium flex-1"
                style={{ color: 'var(--text-primary)' }}
                onClick={() => {
                  haptic('selection');
                  setAteWithoutGadgets(!ateWithoutGadgets);
                }}
              >
                {getGenderText()}
              </span>
            </label>
            <p className="text-xs mt-2 ml-9" style={{ color: 'var(--text-tertiary)' }}>
              💡 Осознанное питание без отвлечения на телефон или компьютер
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

          {/* Time selector */}
          <div className="mb-6">
            <label
              className="flex items-center gap-2 text-sm font-medium mb-2"
              style={{ color: 'var(--text-secondary)' }}
            >
              <Clock className="w-4 h-4" />
              Время приёма пищи
            </label>
            <input
              type="time"
              value={selectedTime}
              onChange={(e) => setSelectedTime(e.target.value)}
              className="input-field"
            />
          </div>

          {/* Hunger before meal */}
          <div className="mb-6">
            <label
              className="text-sm font-medium mb-3 block"
              style={{ color: 'var(--text-secondary)' }}
            >
              Голод перед едой (опционально)
            </label>
            <div className="flex gap-2">
              {[1, 2, 3, 4, 5].map((level) => (
                <button
                  key={level}
                  onClick={() => {
                    haptic('selection');
                    setHungerBefore(hungerBefore === level ? undefined : level);
                  }}
                  className="flex-1 py-3 px-2 rounded-xl text-sm font-medium transition-all"
                  style={{
                    background:
                      hungerBefore === level ? 'var(--accent)' : 'var(--bg-secondary)',
                    color: hungerBefore === level ? 'white' : 'var(--text-primary)',
                  }}
                >
                  {level === 1 && '😐'}
                  {level === 2 && '🙂'}
                  {level === 3 && '😋'}
                  {level === 4 && '😤'}
                  {level === 5 && '🤤'}
                  <div className="text-xs mt-1">{level}</div>
                </button>
              ))}
            </div>
            <p className="text-xs mt-2" style={{ color: 'var(--text-tertiary)' }}>
              1 - очень голоден, 5 - очень сыт
            </p>
          </div>

          {/* Fullness after meal */}
          <div className="mb-6">
            <label
              className="text-sm font-medium mb-3 block"
              style={{ color: 'var(--text-secondary)' }}
            >
              Сытость после еды (опционально)
            </label>
            <div className="flex gap-2">
              {[1, 2, 3, 4, 5].map((level) => (
                <button
                  key={level}
                  onClick={() => {
                    haptic('selection');
                    setFullnessAfter(fullnessAfter === level ? undefined : level);
                  }}
                  className="flex-1 py-3 px-2 rounded-xl text-sm font-medium transition-all"
                  style={{
                    background:
                      fullnessAfter === level ? 'var(--accent)' : 'var(--bg-secondary)',
                    color: fullnessAfter === level ? 'white' : 'var(--text-primary)',
                  }}
                >
                  {level === 1 && '😐'}
                  {level === 2 && '🙂'}
                  {level === 3 && '😋'}
                  {level === 4 && '😤'}
                  {level === 5 && '🤤'}
                  <div className="text-xs mt-1">{level}</div>
                </button>
              ))}
            </div>
            <p className="text-xs mt-2" style={{ color: 'var(--text-tertiary)' }}>
              💡 Отметь сытость через 10-15 минут после еды
            </p>
            <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>
              1 - совсем не насытился, 5 - очень сыт
            </p>
          </div>

          {/* Ate without gadgets */}
          <div className="mb-6">
            <label className="flex items-center gap-3 cursor-pointer">
              <div
                className="flex items-center justify-center w-6 h-6 rounded-lg border-2 transition-all"
                style={{
                  borderColor: ateWithoutGadgets ? 'var(--accent)' : 'var(--border)',
                  background: ateWithoutGadgets ? 'var(--accent)' : 'transparent',
                }}
                onClick={() => {
                  haptic('selection');
                  setAteWithoutGadgets(!ateWithoutGadgets);
                }}
              >
                {ateWithoutGadgets && <Check className="w-4 h-4 text-white" />}
              </div>
              <span
                className="text-sm font-medium flex-1"
                style={{ color: 'var(--text-primary)' }}
                onClick={() => {
                  haptic('selection');
                  setAteWithoutGadgets(!ateWithoutGadgets);
                }}
              >
                {getGenderText()}
              </span>
            </label>
            <p className="text-xs mt-2 ml-9" style={{ color: 'var(--text-tertiary)' }}>
              💡 Осознанное питание без отвлечения на телефон или компьютер
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
