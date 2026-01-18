// No Subscription page - shown when user doesn't have active subscription

import { Layout, Card, Button } from '../components/Layout';
import { useTelegram } from '../hooks/useTelegram';
import { Lock, CreditCard, ExternalLink } from 'lucide-react';

export function NoSubscription() {
  const { close } = useTelegram();

  return (
    <Layout>
      <div className="flex flex-col items-center text-center pt-12 animate-in">
        <div
          className="w-20 h-20 rounded-full flex items-center justify-center mb-8"
          style={{ background: 'var(--warning-soft)' }}
        >
          <Lock className="w-10 h-10" style={{ color: 'var(--warning)' }} />
        </div>

        <h1 className="text-2xl font-bold mb-3" style={{ color: 'var(--text-primary)' }}>
          Требуется подписка
        </h1>

        <p className="text-sm mb-8 max-w-xs" style={{ color: 'var(--text-secondary)' }}>
          Для доступа к ассистенту привычек необходима активная подписка на марафон
        </p>

        <Card className="w-full mb-6">
          <div className="flex items-start gap-4">
            <div
              className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0"
              style={{ background: 'var(--accent-soft)' }}
            >
              <CreditCard className="w-6 h-6" style={{ color: 'var(--accent)' }} />
            </div>
            <div className="text-left">
              <h3 className="font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>
                Что входит в подписку
              </h3>
              <ul className="text-sm space-y-1" style={{ color: 'var(--text-secondary)' }}>
                <li>• Тренировки «повторяй за мной»</li>
                <li>• Ассистент привычек</li>
                <li>• Food tracker с AI-анализом</li>
                <li>• Персональные итоги и обзоры</li>
                <li>• Закрытое комьюнити</li>
              </ul>
            </div>
          </div>
        </Card>

        <div className="w-full space-y-3">
          <Button
            onClick={() => {
              // Return to bot to pay
              close();
            }}
            className="w-full"
          >
            Оформить подписку
            <ExternalLink className="w-4 h-4 ml-2" />
          </Button>

          <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
            Оплата происходит через бота
          </p>
        </div>
      </div>
    </Layout>
  );
}

export default NoSubscription;
