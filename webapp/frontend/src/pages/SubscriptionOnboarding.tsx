// Subscription Onboarding - показываем когда нет подписки
import { useState } from 'react';
import { Layout, Button } from '../components/Layout';
import { useTelegram } from '../hooks/useTelegram';
import { ChevronLeft, ChevronRight, Sparkles } from 'lucide-react';

const MONTH_PRICE = import.meta.env.VITE_MONTH_PRICE || '490';

const slides = [
  {
    title: 'Твой личный трекер здоровья',
    items: [
      'AI-анализ питания по фото',
      'Умный трекер сна',
      'Еженедельные обзоры прогресса',
      'Всё в одном месте, всегда под рукой'
    ]
  },
  {
    title: 'Питание без подсчёта калорий',
    items: [
      'Сфотографировал еду — готово!',
      'AI опишет блюдо и категории',
      'Отмечай голод и сытость',
      'Видишь реальную картину питания'
    ]
  },
  {
    title: 'Сон, который меняет всё',
    items: [
      'Записывай время сна за секунду',
      'Отслеживай качество и самочувствие',
      'Анализируй паттерны',
      'Высыпайся и побеждай'
    ]
  },
  {
    title: 'Еженедельные обзоры',
    items: [
      'AI анализирует твою неделю',
      'Персональные рекомендации',
      'Видишь динамику изменений',
      'Понимаешь что работает, а что нет'
    ]
  },
  {
    title: 'Идеальная пара с марафоном',
    items: [
      'Марафон даёт знания и мотивацию',
      'Трекер показывает реальный прогресс',
      'Вместе они создают систему',
      'Которая реально работает'
    ]
  },
  {
    title: `${MONTH_PRICE}₽/месяц`,
    items: [
      'за фитнесс марафон и персонального фитнесс-ассистента',
      'Отменить можно в любой момент'
    ],
    isFinal: true
  }
];

export function SubscriptionOnboarding() {
  const { haptic, openLink } = useTelegram();
  const [currentSlide, setCurrentSlide] = useState(0);

  const handleNext = () => {
    haptic('light');
    if (currentSlide < slides.length - 1) {
      setCurrentSlide(currentSlide + 1);
    }
  };

  const handlePrev = () => {
    haptic('light');
    if (currentSlide > 0) {
      setCurrentSlide(currentSlide - 1);
    }
  };

  const handleSubscribe = () => {
    haptic('medium');
    // Открываем бота с командой /start для оформления подписки
    openLink('https://t.me/YourBodyPet_bot?start=subscribe');
  };

  const slide = slides[currentSlide];

  return (
    <Layout>
      <div className="flex flex-col h-full pb-32">
        {/* Sad cat intro (только на первом слайде) */}
        {currentSlide === 0 && (
          <div className="text-center mb-4 animate-in">
            <div className="mb-4">
              <img
                src="/sad-cat.png"
                alt="Sad cat"
                className="w-32 h-32 mx-auto rounded-3xl object-cover"
                style={{ boxShadow: '0 8px 32px rgba(0,0,0,0.12)' }}
              />
            </div>
            <h1 className="text-xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>
              Этот котик грустит
            </h1>
            <p className="text-sm mb-4" style={{ color: 'var(--text-secondary)' }}>
              Потому что у тебя нет подписки. А ещё он с удовольствием расскажет про неё подробнее!
            </p>
          </div>
        )}

        {/* Slide content */}
        <div className="flex-1 animate-in overflow-y-auto">
          <h2 className="text-2xl font-bold mb-6 text-center" style={{ color: 'var(--text-primary)' }}>
            {slide.title}
          </h2>

          <div className="space-y-4 mb-8">
            {slide.items.map((item, index) => (
              <div
                key={index}
                className="flex items-start gap-3 p-4 rounded-2xl"
                style={{ background: 'var(--bg-secondary)' }}
              >
                {!slide.isFinal && (
                  <div
                    className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"
                    style={{ background: 'var(--accent)' }}
                  >
                    <span className="text-white text-sm">✓</span>
                  </div>
                )}
                <p
                  className="text-base"
                  style={{
                    color: 'var(--text-primary)',
                    lineHeight: 1.5
                  }}
                >
                  {item}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Fixed navigation at bottom */}
        <div className="fixed bottom-0 left-0 right-0 p-4 pb-8" style={{ background: 'var(--bg-primary)' }}>
          {/* Progress dots */}
          <div className="flex justify-center gap-2 mb-4">
            {slides.map((_, index) => (
              <div
                key={index}
                className="h-2 rounded-full transition-all"
                style={{
                  width: index === currentSlide ? '24px' : '8px',
                  background: index === currentSlide ? 'var(--accent)' : 'var(--bg-secondary)'
                }}
              />
            ))}
          </div>

          {/* Navigation */}
          <div className="flex gap-3">
            {currentSlide > 0 && (
              <button
                onClick={handlePrev}
                className="p-4 rounded-2xl flex items-center justify-center"
                style={{ background: 'var(--bg-secondary)' }}
              >
                <ChevronLeft className="w-6 h-6" style={{ color: 'var(--text-primary)' }} />
              </button>
            )}

            <Button
              onClick={slide.isFinal ? handleSubscribe : handleNext}
              className="flex-1"
            >
              {slide.isFinal ? (
                <>
                  <Sparkles className="w-5 h-5 mr-2" />
                  Оформить подписку
                </>
              ) : (
                <>
                  Далее
                  <ChevronRight className="w-5 h-5 ml-2" />
                </>
              )}
            </Button>
          </div>
        </div>
      </div>
    </Layout>
  );
}
