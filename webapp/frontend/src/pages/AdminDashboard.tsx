// Admin Dashboard - аналитика для администраторов

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Layout, Card, LoadingSpinner, EmptyState, Button } from '../components/Layout';
import { api } from '../api/client';
import { ArrowLeft, Users, DollarSign, TrendingUp, BarChart3, Gift } from 'lucide-react';

interface AdminStats {
  users: { total: number; active: number; expired: number; new_7d: number; new_30d: number };
  revenue: { month: number; total: number };
  conversion: { paid_total: number; started_total: number; rate: number };
  churn: { reasons: Record<string, number> };
  engagement: { avg_food_per_day: number; features: Record<string, number> };
  retention: { auto_renewal_count: number; auto_renewal_pct: number };
  charts: {
    daily_users: Array<{ date: string; count: number }>;
    daily_revenue: Array<{ date: string; amount: number }>;
  };
  referrals: { total_referrals: number; total_paid: number; total_rewards: number };
}

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="p-3 rounded-xl" style={{ background: 'var(--bg-secondary)' }}>
      <div className="text-xs mb-1" style={{ color: 'var(--text-tertiary)' }}>{label}</div>
      <div className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>{value}</div>
      {sub && <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>{sub}</div>}
    </div>
  );
}

function MiniChart({ data, color }: { data: Array<{ value: number }>; color: string }) {
  if (!data.length) return null;
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <div className="flex items-end gap-[2px] h-12">
      {data.map((d, i) => (
        <div
          key={i}
          className="flex-1 rounded-sm min-h-[2px]"
          style={{
            height: `${(d.value / max) * 100}%`,
            background: color,
            opacity: 0.7 + (d.value / max) * 0.3,
          }}
        />
      ))}
    </div>
  );
}

export function AdminDashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getAdminStats()
      .then((data) => setStats(data as unknown as AdminStats))
      .catch((err) => setError(err.message || 'Access denied'))
      .finally(() => setIsLoading(false));
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

  if (error || !stats) {
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
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => navigate('/')}
          className="p-2 rounded-xl"
          style={{ background: 'var(--bg-glass)' }}
        >
          <ArrowLeft className="w-5 h-5" style={{ color: 'var(--text-primary)' }} />
        </button>
        <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
          Аналитика
        </h1>
      </div>

      <div className="space-y-4">
        {/* Users */}
        <Card>
          <div className="flex items-center gap-2 mb-3">
            <Users className="w-5 h-5" style={{ color: 'var(--accent)' }} />
            <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>Пользователи</h3>
          </div>
          <div className="grid grid-cols-3 gap-2 mb-3">
            <StatCard label="Всего" value={stats.users.total} />
            <StatCard label="Активные" value={stats.users.active} />
            <StatCard label="Истекшие" value={stats.users.expired} />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <StatCard label="Новые (7д)" value={stats.users.new_7d} />
            <StatCard label="Новые (30д)" value={stats.users.new_30d} />
          </div>
          {stats.charts.daily_users.length > 0 && (
            <div className="mt-3">
              <MiniChart
                data={stats.charts.daily_users.map((d) => ({ value: d.count }))}
                color="var(--accent)"
              />
            </div>
          )}
        </Card>

        {/* Revenue */}
        <Card>
          <div className="flex items-center gap-2 mb-3">
            <DollarSign className="w-5 h-5" style={{ color: 'var(--success)' }} />
            <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>Выручка</h3>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <StatCard label="За месяц" value={`${stats.revenue.month.toLocaleString()} ₽`} />
            <StatCard label="Всего" value={`${stats.revenue.total.toLocaleString()} ₽`} />
          </div>
          {stats.charts.daily_revenue.length > 0 && (
            <div className="mt-3">
              <MiniChart
                data={stats.charts.daily_revenue.map((d) => ({ value: d.amount }))}
                color="var(--success)"
              />
            </div>
          )}
        </Card>

        {/* Conversion & Retention */}
        <Card>
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp className="w-5 h-5" style={{ color: 'var(--warning)' }} />
            <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>Конверсия и Retention</h3>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <StatCard label="Конверсия" value={`${(stats.conversion.rate * 100).toFixed(0)}%`} sub={`${stats.conversion.paid_total}/${stats.conversion.started_total}`} />
            <StatCard label="Автопродление" value={`${(stats.retention.auto_renewal_pct * 100).toFixed(0)}%`} sub={`${stats.retention.auto_renewal_count} чел.`} />
          </div>
        </Card>

        {/* Engagement */}
        <Card>
          <div className="flex items-center gap-2 mb-3">
            <BarChart3 className="w-5 h-5" style={{ color: 'var(--accent)' }} />
            <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>Вовлечённость</h3>
          </div>
          <StatCard label="Среднее кол-во записей еды/день" value={stats.engagement.avg_food_per_day.toFixed(1)} />
        </Card>

        {/* Churn Reasons */}
        {Object.keys(stats.churn.reasons).length > 0 && (
          <Card>
            <h3 className="font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>Причины отмены</h3>
            <div className="space-y-2">
              {Object.entries(stats.churn.reasons)
                .sort(([, a], [, b]) => b - a)
                .map(([reason, count]) => {
                  const total = Object.values(stats.churn.reasons).reduce((s, v) => s + v, 0);
                  const pct = total > 0 ? (count / total) * 100 : 0;
                  return (
                    <div key={reason}>
                      <div className="flex justify-between text-sm mb-1">
                        <span style={{ color: 'var(--text-primary)' }}>{reason}</span>
                        <span style={{ color: 'var(--text-tertiary)' }}>{count}</span>
                      </div>
                      <div className="h-2 rounded-full" style={{ background: 'var(--bg-secondary)' }}>
                        <div
                          className="h-2 rounded-full"
                          style={{ width: `${pct}%`, background: 'var(--error)' }}
                        />
                      </div>
                    </div>
                  );
                })}
            </div>
          </Card>
        )}

        {/* Referrals */}
        <Card>
          <div className="flex items-center gap-2 mb-3">
            <Gift className="w-5 h-5" style={{ color: 'var(--accent)' }} />
            <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>Рефералы</h3>
          </div>
          <div className="grid grid-cols-3 gap-2">
            <StatCard label="Всего" value={stats.referrals.total_referrals} />
            <StatCard label="Оплатили" value={stats.referrals.total_paid} />
            <StatCard label="Награды" value={stats.referrals.total_rewards} />
          </div>
        </Card>
      </div>
    </Layout>
  );
}

export default AdminDashboard;
