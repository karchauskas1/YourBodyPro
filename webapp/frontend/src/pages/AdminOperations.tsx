// Admin Operations - ежедневный контроль оплат, доступов и отмен

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Layout, Card, LoadingSpinner, EmptyState, Button } from '../components/Layout';
import { api, type AdminOperations as AdminOperationsData } from '../api/client';
import { AlertTriangle, ArrowLeft, Ban, Clock, CreditCard, KeyRound, RefreshCw, UserCog } from 'lucide-react';

function StatCard({ label, value, tone = 'default' }: { label: string; value: string | number; tone?: 'default' | 'warning' | 'danger' | 'success' }) {
  const color = tone === 'danger'
    ? 'var(--error)'
    : tone === 'warning'
      ? 'var(--warning)'
      : tone === 'success'
        ? 'var(--success)'
        : 'var(--text-primary)';

  return (
    <div className="p-3 rounded-xl" style={{ background: 'var(--bg-secondary)' }}>
      <div className="text-xs mb-1" style={{ color: 'var(--text-tertiary)' }}>{label}</div>
      <div className="text-xl font-bold" style={{ color }}>{value}</div>
    </div>
  );
}

function formatDate(ts?: number): string {
  if (!ts) return '—';
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(ts * 1000));
}

function reasonLabel(reason: string): string {
  const labels: Record<string, string> = {
    price: 'Дорого',
    time: 'Нет времени',
    tech: 'Тех. проблемы',
    other_service: 'Другой формат',
    other: 'Другая причина',
    admin_revoke: 'Отмена админом',
    payment_failed: 'Не прошла оплата',
    webapp: 'WebApp',
  };

  const prefixes: Record<string, string> = {
    renewal_off: 'Отключил автопродление',
    card_unlinked: 'Отвязал карту',
    immediate_cancel: 'Закрыл доступ сразу',
  };

  for (const [prefix, label] of Object.entries(prefixes)) {
    const fullPrefix = `${prefix}_`;
    if (reason.startsWith(fullPrefix)) {
      const base = reason.slice(fullPrefix.length);
      return `${label}: ${labels[base] || base}`;
    }
  }

  return labels[reason] || reason || 'Не указано';
}

export function AdminOperations() {
  const navigate = useNavigate();
  const [data, setData] = useState<AdminOperationsData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = () => {
    setIsLoading(true);
    setError(null);
    api.getAdminOperations()
      .then(setData)
      .catch((err) => setError(err.message || 'Access denied'))
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    loadData();
  }, []);

  if (isLoading) {
    return (
      <Layout>
        <div className="flex items-center justify-center min-h-[60vh]">
          <LoadingSpinner size="lg" />
        </div>
      </Layout>
    );
  }

  if (error || !data) {
    return (
      <Layout>
        <EmptyState
          title="Нет доступа"
          description={error || 'Не удалось загрузить данные'}
          action={<Button onClick={() => navigate('/')} variant="secondary">На главную</Button>}
        />
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/admin')}
            className="p-2 rounded-xl"
            style={{ background: 'var(--bg-glass)' }}
          >
            <ArrowLeft className="w-5 h-5" style={{ color: 'var(--text-primary)' }} />
          </button>
          <div>
            <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
              Контроль
            </h1>
            <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
              Оплаты, доступы, отмены
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => navigate('/admin/console')}
            className="p-2 rounded-xl"
            style={{ background: 'var(--accent)' }}
          >
            <UserCog className="w-5 h-5" style={{ color: '#fff' }} />
          </button>
          <button
            onClick={loadData}
            className="p-2 rounded-xl"
            style={{ background: 'var(--bg-glass)' }}
          >
            <RefreshCw className="w-5 h-5" style={{ color: 'var(--text-primary)' }} />
          </button>
        </div>
      </div>

      <div className="space-y-4">
        <Card>
          <div className="flex items-center gap-2 mb-3">
            <KeyRound className="w-5 h-5" style={{ color: 'var(--accent)' }} />
            <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>Доступ</h3>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <StatCard label="Активные" value={data.access.active} tone="success" />
            <StatCard label="Истёкшие в базе" value={data.access.expired_unprocessed} tone={data.access.expired_unprocessed > 0 ? 'warning' : 'default'} />
            <StatCard label="Истекают за 24ч" value={data.access.expiring.within_1_days} />
            <StatCard label="Открытые события" value={data.access.open_events} tone={data.access.open_events > 0 ? 'danger' : 'default'} />
          </div>
        </Card>

        <Card>
          <div className="flex items-center gap-2 mb-3">
            <CreditCard className="w-5 h-5" style={{ color: 'var(--success)' }} />
            <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>Оплаты</h3>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <StatCard label="Оплат сегодня" value={data.payments.succeeded_today} tone="success" />
            <StatCard label="Выручка сегодня" value={`${data.payments.revenue_today.toLocaleString()} ₽`} tone="success" />
            <StatCard label="Pending всего" value={data.payments.pending_total} />
            <StatCard label="Pending > 15 мин" value={data.payments.pending_old} tone={data.payments.pending_old > 0 ? 'warning' : 'default'} />
          </div>
        </Card>

        <Card>
          <div className="flex items-center gap-2 mb-3">
            <RefreshCw className="w-5 h-5" style={{ color: 'var(--warning)' }} />
            <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>Продление</h3>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <StatCard label="Автопродление" value={data.retention.auto_renewal_enabled} tone={data.retention.auto_renewal_enabled > 0 ? 'success' : 'warning'} />
            <StatCard label="Сохранённые карты" value={data.retention.saved_payment_methods} tone={data.retention.saved_payment_methods > 0 ? 'success' : 'warning'} />
            <StatCard label="Карта без продления" value={data.retention.auto_renewal_disabled_with_card} tone={data.retention.auto_renewal_disabled_with_card > 0 ? 'warning' : 'default'} />
            <StatCard label="Ошибки списаний" value={data.retention.auto_renewal_failures} tone={data.retention.auto_renewal_failures > 0 ? 'danger' : 'default'} />
            <StatCard label="Отключили продление" value={data.retention.renewal_disabled_total} />
            <StatCard label="Отвязали карту" value={data.retention.cards_unlinked_total} />
            <StatCard label="Закрыли сразу" value={data.retention.immediate_cancel_total} tone={data.retention.immediate_cancel_total > 0 ? 'warning' : 'default'} />
          </div>
        </Card>

        {data.events.length > 0 && (
          <Card>
            <div className="flex items-center gap-2 mb-3">
              <AlertTriangle className="w-5 h-5" style={{ color: 'var(--error)' }} />
              <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>Требует внимания</h3>
            </div>
            <div className="space-y-3">
              {data.events.map((event) => (
                <div key={event.id} className="p-3 rounded-xl" style={{ background: 'var(--bg-secondary)' }}>
                  <div className="flex justify-between gap-3 mb-1">
                    <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{event.event_type}</span>
                    <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{formatDate(event.created_at)}</span>
                  </div>
                  <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{event.message}</p>
                </div>
              ))}
            </div>
          </Card>
        )}

        <Card>
          <div className="flex items-center gap-2 mb-3">
            <Clock className="w-5 h-5" style={{ color: 'var(--warning)' }} />
            <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>Старые pending</h3>
          </div>
          {data.payments.old_pending.length === 0 ? (
            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Нет зависших платежей старше 15 минут</p>
          ) : (
            <div className="space-y-2">
              {data.payments.old_pending.map((payment) => (
                <div key={payment.payment_id} className="flex justify-between gap-3 text-sm">
                  <span style={{ color: 'var(--text-primary)' }}>ID {payment.user_id}</span>
                  <span style={{ color: 'var(--text-secondary)' }}>{payment.status} · {formatDate(payment.created_at)}</span>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card>
          <div className="flex items-center gap-2 mb-3">
            <Ban className="w-5 h-5" style={{ color: 'var(--error)' }} />
            <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>Отмены</h3>
          </div>
          <div className="grid grid-cols-2 gap-2 mb-3">
            <StatCard label="Сегодня" value={data.cancellations.today} tone={data.cancellations.today > 0 ? 'warning' : 'default'} />
            <StatCard label="Всего причин" value={Object.values(data.cancellations.reasons).reduce((sum, value) => sum + value, 0)} />
          </div>

          {Object.keys(data.cancellations.reasons).length > 0 && (
            <div className="space-y-2 mb-4">
              {Object.entries(data.cancellations.reasons)
                .sort(([, a], [, b]) => b - a)
                .map(([reason, count]) => (
                  <div key={reason} className="flex justify-between text-sm">
                    <span style={{ color: 'var(--text-primary)' }}>{reasonLabel(reason)}</span>
                    <span style={{ color: 'var(--text-tertiary)' }}>{count}</span>
                  </div>
                ))}
            </div>
          )}

          {data.cancellations.recent.length > 0 && (
            <div className="space-y-2">
              {data.cancellations.recent.map((item) => (
                <div key={`${item.user_id}-${item.created_at}`} className="p-3 rounded-xl" style={{ background: 'var(--bg-secondary)' }}>
                  <div className="flex justify-between gap-3 text-sm">
                    <span style={{ color: 'var(--text-primary)' }}>
                      {item.username ? `@${item.username}` : item.full_name || `ID ${item.user_id}`}
                    </span>
                    <span style={{ color: 'var(--text-tertiary)' }}>{formatDate(item.created_at)}</span>
                  </div>
                  <div className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>{reasonLabel(item.reason)}</div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </Layout>
  );
}

export default AdminOperations;
