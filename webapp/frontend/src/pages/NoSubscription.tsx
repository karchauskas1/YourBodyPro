// No Subscription page - shown when user doesn't have active subscription

import { useNavigate } from 'react-router-dom';
import { Layout, Card, Button } from '../components/Layout';
import { useTelegram } from '../hooks/useTelegram';
import { Check, Sparkles } from 'lucide-react';

export function NoSubscription() {
  const navigate = useNavigate();
  const { haptic, close } = useTelegram();

  const benefits = [
    {
      emoji: '🍽️',
      title: 'Food Tracker с AI',
      description: 'Распознавание еды по фото, анализ баланса, вечерние итоги',
    },
    {
      emoji: '😴',
      title: 'Трекер сна',
      description: 'Отслеживание качества сна и связи с питанием',
    },
    {
      emoji: '📊',
      title: 'Недельные обзоры',
      description: 'Персональные паттерны и инсайты каждое воскресенье',
    },
    {
      emoji: '😋',
      title: 'Голод и сытость',
      description: 'Учись понимать сигналы своего тела',
    },
    {
      emoji: '🎯',
      title: 'Персональные цели',
      description: 'Настройка под твои задачи: похудение, набор массы или поддержание',
    },
    {
      emoji: '⏰',
      title: 'Гибкие уведомления',
      description: 'Настрой время под свой график в любом часовом поясе',
    },
    {
      emoji: '🏋️',
      title: 'Тренировки',
      description: 'Марафон с Настей: тренировки "повторяй за мной"',
    },
    {
      emoji: '💬',
      title: 'Комьюнити',
      description: 'Закрытое комьюнити единомышленников',
    },
  ];

  const handleSubscribe = () => {
    haptic('medium');
    // Return to bot to purchase subscription
    close();
  };

  return (
    <Layout>
      <div className="flex flex-col items-center text-center pt-6 pb-6 animate-in">
        {/* Sad cat */}
        <div
          className="w-32 h-32 rounded-full flex items-center justify-center mb-6"
          style={{ background: 'var(--bg-secondary)' }}
        >
          <span className="text-7xl">😿</span>
        </div>

        <h1 className="text-2xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>
          Этот котик грустит...
        </h1>

        <p className="text-base mb-8" style={{ color: 'var(--text-secondary)' }}>
          Потому что у тебя нет подписки
          <br />
          Но он с удовольствием про неё расскажет! 😺
        </p>

        {/* Benefits */}
        <div className="w-full space-y-3 mb-8">
          <div className="flex items-center gap-2 mb-4">
            <Sparkles className="w-5 h-5" style={{ color: 'var(--accent)' }} />
            <h2 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
              Что даёт подписка:
            </h2>
          </div>

          {benefits.map((benefit, index) => (
            <Card key={index} className="text-left">
              <div className="flex items-start gap-3">
                <span className="text-2xl flex-shrink-0">{benefit.emoji}</span>
                <div className="flex-1">
                  <h3 className="font-semibold mb-1 text-sm" style={{ color: 'var(--text-primary)' }}>
                    {benefit.title}
                  </h3>
                  <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                    {benefit.description}
                  </p>
                </div>
                <Check className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--success)' }} />
              </div>
            </Card>
          ))}
        </div>

        {/* CTA */}
        <Button onClick={handleSubscribe} className="w-full mb-4">
          <Sparkles className="w-5 h-5 mr-2" />
          Узнать про блага подписки
        </Button>

        <button
          onClick={() => {
            haptic('light');
            navigate('/');
          }}
          className="text-sm"
          style={{ color: 'var(--text-tertiary)' }}
        >
          Вернуться назад
        </button>
      </div>
    </Layout>
  );
}

export default NoSubscription;
