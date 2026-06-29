import { useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowLeft,
  Ban,
  CalendarPlus,
  CheckCircle2,
  CreditCard,
  KeyRound,
  Link2,
  RefreshCw,
  Search,
  Send,
  ShieldCheck,
  UserRound,
  Users,
  WalletCards,
  XCircle,
} from 'lucide-react';
import {
  api,
  type AdminConsoleSummary,
  type AdminEventItem,
  type AdminPaymentItem,
  type AdminUserDetail,
  type AdminUserListItem,
  type Paginated,
} from '../api/client';
import { Button, LoadingSpinner } from '../components/Layout';

type Tab = 'users' | 'payments' | 'events';

const userFilters = [
  { value: 'all', label: 'Все' },
  { value: 'active', label: 'Активные' },
  { value: 'expiring', label: 'Скоро истекают' },
  { value: 'expired', label: 'Истёкшие' },
  { value: 'renewal', label: 'Автопродление' },
  { value: 'issues', label: 'Проблемы' },
];

const paymentFilters = [
  { value: 'all', label: 'Все' },
  { value: 'succeeded', label: 'Успешные' },
  { value: 'pending', label: 'Pending' },
  { value: 'canceled', label: 'Отменённые' },
];

function formatDate(ts?: number | null): string {
  if (!ts) return '—';
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(ts * 1000));
}

function formatMoney(value: number): string {
  return `${value.toLocaleString('ru-RU')} ₽`;
}

function userTitle(user: { username?: string; full_name?: string; user_id: number }): string {
  if (user.username) return `@${user.username}`;
  if (user.full_name) return user.full_name;
  return `ID ${user.user_id}`;
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    active: 'Активен',
    expiring: 'Скоро истекает',
    expired: 'Истёк',
    no_access: 'Без доступа',
  };
  return labels[status] || status;
}

function statusColor(status: string): string {
  if (status === 'active') return 'var(--success)';
  if (status === 'expiring') return 'var(--warning)';
  if (status === 'expired') return 'var(--error)';
  return 'var(--text-tertiary)';
}

function reasonLabel(reason: string): string {
  const labels: Record<string, string> = {
    price: 'Дорого',
    time: 'Нет времени',
    tech: 'Тех. проблемы',
    other_service: 'Другой формат',
    other: 'Другая причина',
    admin_revoke: 'Отмена админом',
    admin_revoke_web: 'Отмена админом',
    card_unlinked_admin: 'Карту отвязал админ',
    payment_failed: 'Не прошла оплата',
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

function Panel({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`glass-card p-4 ${className}`}>{children}</section>;
}

function StatTile({ label, value, tone = 'default' }: { label: string; value: number | string; tone?: 'default' | 'success' | 'warning' | 'danger' }) {
  const color = tone === 'success'
    ? 'var(--success)'
    : tone === 'warning'
      ? 'var(--warning)'
      : tone === 'danger'
        ? 'var(--error)'
        : 'var(--text-primary)';
  return (
    <div className="rounded-xl p-3" style={{ background: 'var(--bg-secondary)' }}>
      <div className="text-xs mb-1" style={{ color: 'var(--text-tertiary)' }}>{label}</div>
      <div className="text-xl font-bold" style={{ color }}>{value}</div>
    </div>
  );
}

function Segmented({
  items,
  value,
  onChange,
}: {
  items: Array<{ value: string; label: string }>;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <button
          key={item.value}
          onClick={() => onChange(item.value)}
          className="px-3 py-2 rounded-xl text-sm"
          style={{
            background: item.value === value ? 'var(--accent)' : 'var(--bg-secondary)',
            color: item.value === value ? '#fff' : 'var(--text-primary)',
          }}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}

export function AdminConsole() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>('users');
  const [summary, setSummary] = useState<AdminConsoleSummary | null>(null);
  const [users, setUsers] = useState<Paginated<AdminUserListItem> | null>(null);
  const [payments, setPayments] = useState<Paginated<AdminPaymentItem> | null>(null);
  const [events, setEvents] = useState<Paginated<AdminEventItem> | null>(null);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [selectedUser, setSelectedUser] = useState<AdminUserDetail | null>(null);
  const [userStatus, setUserStatus] = useState('all');
  const [paymentStatus, setPaymentStatus] = useState('all');
  const [eventState, setEventState] = useState('open');
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadSummary = () => api.getAdminConsoleSummary().then(setSummary);

  const loadUsers = () => api.getAdminUsers({ status: userStatus, q: query, limit: 50 }).then((data) => {
    setUsers(data);
    if (!selectedUserId && data.items.length > 0) {
      setSelectedUserId(data.items[0].user_id);
    }
  });

  const loadPayments = () => api.getAdminPayments({ status: paymentStatus, q: query, limit: 50 }).then(setPayments);
  const loadEvents = () => api.getAdminEvents({ state: eventState, limit: 50 }).then(setEvents);

  const loadAll = async () => {
    setError(null);
    setIsLoading(true);
    try {
      await Promise.all([loadSummary(), loadUsers(), loadPayments(), loadEvents()]);
    } catch (err: any) {
      setError(err.message || 'Не удалось загрузить админку');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  useEffect(() => {
    loadUsers().catch((err) => setError(err.message || 'Не удалось загрузить клиентов'));
  }, [userStatus]);

  useEffect(() => {
    loadPayments().catch((err) => setError(err.message || 'Не удалось загрузить платежи'));
  }, [paymentStatus]);

  useEffect(() => {
    loadEvents().catch((err) => setError(err.message || 'Не удалось загрузить события'));
  }, [eventState]);

  useEffect(() => {
    if (!selectedUserId) {
      setSelectedUser(null);
      return;
    }
    setDetailLoading(true);
    api.getAdminUserDetail(selectedUserId)
      .then(setSelectedUser)
      .catch((err) => setError(err.message || 'Не удалось загрузить клиента'))
      .finally(() => setDetailLoading(false));
  }, [selectedUserId]);

  const runSearch = async () => {
    setError(null);
    try {
      await Promise.all([loadUsers(), loadPayments()]);
    } catch (err: any) {
      setError(err.message || 'Не удалось выполнить поиск');
    }
  };

  const refreshSelected = async () => {
    await Promise.all([
      loadSummary(),
      loadUsers(),
      loadPayments(),
      loadEvents(),
      selectedUserId ? api.getAdminUserDetail(selectedUserId).then(setSelectedUser) : Promise.resolve(),
    ]);
  };

  const runAction = async (key: string, action: () => Promise<unknown>, success: string) => {
    setActionLoading(key);
    setNotice(null);
    setError(null);
    try {
      await action();
      setNotice(success);
      await refreshSelected();
    } catch (err: any) {
      setError(err.message || 'Действие не выполнено');
    } finally {
      setActionLoading(null);
    }
  };

  const activeUser = selectedUser?.user;

  const tabCounts = useMemo(() => ({
    users: summary?.total_users ?? 0,
    payments: summary?.pending_payments ?? 0,
    events: summary?.open_events ?? 0,
  }), [summary]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  return (
    <div className="min-h-screen px-4 py-5">
      <main className="max-w-6xl mx-auto">
        <div className="flex flex-col gap-4 mb-5 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/admin')}
              className="p-2 rounded-xl"
              style={{ background: 'var(--bg-glass)' }}
            >
              <ArrowLeft className="w-5 h-5" style={{ color: 'var(--text-primary)' }} />
            </button>
            <div>
              <h1 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>Админ-пульт</h1>
              <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Клиенты, платежи, доступы, тревоги</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => navigate('/admin')}
              className="px-3 py-2 rounded-xl text-sm"
              style={{ background: 'var(--bg-secondary)', color: 'var(--text-primary)' }}
            >
              Аналитика
            </button>
            <button
              onClick={() => navigate('/admin/ops')}
              className="px-3 py-2 rounded-xl text-sm"
              style={{ background: 'var(--bg-secondary)', color: 'var(--text-primary)' }}
            >
              Контроль
            </button>
            <button
              onClick={loadAll}
              className="p-2 rounded-xl"
              style={{ background: 'var(--bg-secondary)' }}
            >
              <RefreshCw className="w-5 h-5" style={{ color: 'var(--text-primary)' }} />
            </button>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-xl text-sm" style={{ background: 'var(--error-soft)', color: 'var(--error)' }}>
            {error}
          </div>
        )}
        {notice && (
          <div className="mb-4 p-3 rounded-xl text-sm" style={{ background: 'var(--success-soft)', color: 'var(--success)' }}>
            {notice}
          </div>
        )}

        {summary && (
          <div className="grid grid-cols-2 md:grid-cols-6 gap-2 mb-4">
            <StatTile label="Активные" value={summary.active_users} tone="success" />
            <StatTile label="Скоро истекают" value={summary.expiring_3d} tone={summary.expiring_3d > 0 ? 'warning' : 'default'} />
            <StatTile label="Истёкшие" value={summary.expired_users} tone={summary.expired_users > 0 ? 'warning' : 'default'} />
            <StatTile label="Pending" value={summary.pending_payments} tone={summary.old_pending > 0 ? 'warning' : 'default'} />
            <StatTile label="Тревоги" value={summary.open_events} tone={summary.critical_events > 0 ? 'danger' : 'default'} />
            <StatTile label="Карты" value={summary.saved_cards} tone={summary.saved_cards > 0 ? 'success' : 'default'} />
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_420px] gap-4">
          <div className="space-y-4">
            <Panel>
              <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div className="flex gap-2">
                  {([
                    { key: 'users', label: 'Клиенты', icon: Users, count: tabCounts.users },
                    { key: 'payments', label: 'Платежи', icon: CreditCard, count: tabCounts.payments },
                    { key: 'events', label: 'Тревоги', icon: AlertTriangle, count: tabCounts.events },
                  ] as const).map((item) => {
                    const Icon = item.icon;
                    return (
                      <button
                        key={item.key}
                        onClick={() => setTab(item.key)}
                        className="flex items-center gap-2 px-3 py-2 rounded-xl text-sm"
                        style={{
                          background: tab === item.key ? 'var(--accent)' : 'var(--bg-secondary)',
                          color: tab === item.key ? '#fff' : 'var(--text-primary)',
                        }}
                      >
                        <Icon className="w-4 h-4" />
                        {item.label}
                        <span className="text-xs opacity-80">{item.count}</span>
                      </button>
                    );
                  })}
                </div>
                <div className="flex gap-2">
                  <div className="relative flex-1 min-w-[220px]">
                    <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-tertiary)' }} />
                    <input
                      value={query}
                      onChange={(event) => setQuery(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter') runSearch();
                      }}
                      placeholder="ID, username, телефон"
                      className="w-full pl-9 pr-3 py-2 rounded-xl text-sm outline-none"
                      style={{ background: 'var(--bg-secondary)', color: 'var(--text-primary)' }}
                    />
                  </div>
                  <button
                    onClick={runSearch}
                    className="px-3 py-2 rounded-xl text-sm"
                    style={{ background: 'var(--bg-secondary)', color: 'var(--text-primary)' }}
                  >
                    Найти
                  </button>
                </div>
              </div>
            </Panel>

            {tab === 'users' && (
              <Panel>
                <div className="mb-4">
                  <Segmented items={userFilters} value={userStatus} onChange={setUserStatus} />
                </div>
                <div className="space-y-2">
                  {users?.items.map((item) => (
                    <button
                      key={item.user_id}
                      onClick={() => setSelectedUserId(item.user_id)}
                      className="w-full text-left p-3 rounded-xl transition-colors"
                      style={{
                        background: selectedUserId === item.user_id ? 'var(--bg-glass)' : 'var(--bg-secondary)',
                        border: selectedUserId === item.user_id ? '1px solid var(--accent)' : '1px solid transparent',
                      }}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="font-semibold" style={{ color: 'var(--text-primary)' }}>{userTitle(item)}</div>
                          <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                            ID {item.user_id}{item.phone ? ` · ${item.phone}` : ''}
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-sm font-semibold" style={{ color: statusColor(item.status) }}>{statusLabel(item.status)}</div>
                          <div className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{formatDate(item.expires_at)}</div>
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-2 mt-3 text-xs">
                        <span className="px-2 py-1 rounded-lg" style={{ background: 'var(--bg-primary)', color: 'var(--text-secondary)' }}>
                          {formatMoney(item.paid_total)}
                        </span>
                        {item.auto_renewal && <span className="px-2 py-1 rounded-lg" style={{ background: 'var(--success-soft)', color: 'var(--success)' }}>автопродление</span>}
                        {item.has_payment_method && <span className="px-2 py-1 rounded-lg" style={{ background: 'var(--bg-primary)', color: 'var(--text-secondary)' }}>карта</span>}
                        {item.open_events > 0 && <span className="px-2 py-1 rounded-lg" style={{ background: 'var(--error-soft)', color: 'var(--error)' }}>{item.open_events} тревог</span>}
                      </div>
                    </button>
                  ))}
                  {users?.items.length === 0 && (
                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Клиенты не найдены</p>
                  )}
                </div>
              </Panel>
            )}

            {tab === 'payments' && (
              <Panel>
                <div className="mb-4">
                  <Segmented items={paymentFilters} value={paymentStatus} onChange={setPaymentStatus} />
                </div>
                <div className="space-y-2">
                  {payments?.items.map((payment) => (
                    <button
                      key={payment.payment_id}
                      onClick={() => {
                        setSelectedUserId(payment.user_id);
                        setTab('users');
                      }}
                      className="w-full text-left p-3 rounded-xl"
                      style={{ background: 'var(--bg-secondary)' }}
                    >
                      <div className="flex justify-between gap-3">
                        <div>
                          <div className="font-semibold" style={{ color: 'var(--text-primary)' }}>{formatMoney(payment.amount)}</div>
                          <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>{userTitle(payment)}</div>
                        </div>
                        <div className="text-right">
                          <div className="text-sm" style={{ color: payment.status === 'succeeded' ? 'var(--success)' : 'var(--warning)' }}>{payment.status}</div>
                          <div className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{formatDate(payment.created_at)}</div>
                        </div>
                      </div>
                      <div className="text-xs mt-2 truncate" style={{ color: 'var(--text-tertiary)' }}>{payment.payment_id}</div>
                    </button>
                  ))}
                  {payments?.items.length === 0 && (
                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Платежи не найдены</p>
                  )}
                </div>
              </Panel>
            )}

            {tab === 'events' && (
              <Panel>
                <div className="mb-4">
                  <Segmented
                    items={[
                      { value: 'open', label: 'Открытые' },
                      { value: 'resolved', label: 'Закрытые' },
                      { value: 'all', label: 'Все' },
                    ]}
                    value={eventState}
                    onChange={setEventState}
                  />
                </div>
                <div className="space-y-2">
                  {events?.items.map((event) => (
                    <div key={event.id} className="p-3 rounded-xl" style={{ background: 'var(--bg-secondary)' }}>
                      <div className="flex justify-between gap-3">
                        <div>
                          <div className="font-semibold" style={{ color: event.severity === 'critical' ? 'var(--error)' : 'var(--text-primary)' }}>
                            {event.event_type}
                          </div>
                          <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                            {event.user_id ? userTitle(event as any) : 'Без клиента'} · {formatDate(event.created_at)}
                          </div>
                        </div>
                        {!event.resolved && (
                          <button
                            onClick={() => runAction(`event-${event.id}`, () => api.resolveAdminEvent(event.id), 'Тревога закрыта')}
                            className="px-3 py-2 rounded-xl text-xs"
                            style={{ background: 'var(--bg-primary)', color: 'var(--text-primary)' }}
                          >
                            Закрыть
                          </button>
                        )}
                      </div>
                      <p className="text-sm mt-2" style={{ color: 'var(--text-secondary)' }}>{event.message}</p>
                    </div>
                  ))}
                  {events?.items.length === 0 && (
                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Тревог нет</p>
                  )}
                </div>
              </Panel>
            )}
          </div>

          <aside className="space-y-4">
            <Panel>
              {detailLoading ? (
                <div className="flex justify-center py-12"><LoadingSpinner /></div>
              ) : !activeUser ? (
                <div className="text-center py-10">
                  <UserRound className="w-8 h-8 mx-auto mb-2" style={{ color: 'var(--text-tertiary)' }} />
                  <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Выберите клиента</p>
                </div>
              ) : (
                <div className="space-y-4">
                  <div>
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <h2 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>{userTitle(activeUser)}</h2>
                        <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                          ID {activeUser.user_id}{activeUser.phone ? ` · ${activeUser.phone}` : ''}
                        </p>
                      </div>
                      <span className="px-2 py-1 rounded-lg text-xs font-semibold" style={{ background: 'var(--bg-secondary)', color: statusColor(activeUser.status) }}>
                        {statusLabel(activeUser.status)}
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <StatTile label="Доступ до" value={formatDate(activeUser.expires_at)} tone={activeUser.status === 'expired' ? 'danger' : 'default'} />
                    <StatTile label="Дней осталось" value={activeUser.days_left} tone={activeUser.status === 'expiring' ? 'warning' : 'default'} />
                    <StatTile label="Платежей" value={selectedUser!.payments.length} />
                    <StatTile label="Сумма" value={formatMoney(activeUser.paid_total || selectedUser!.payments.reduce((sum, payment) => payment.status === 'succeeded' ? sum + payment.amount : sum, 0))} />
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div className="p-3 rounded-xl" style={{ background: 'var(--bg-secondary)' }}>
                      <div className="flex items-center gap-2 mb-1">
                        <ShieldCheck className="w-4 h-4" style={{ color: activeUser.auto_renewal ? 'var(--success)' : 'var(--text-tertiary)' }} />
                        <span className="text-sm" style={{ color: 'var(--text-primary)' }}>Автопродление</span>
                      </div>
                      <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                        {activeUser.auto_renewal ? 'включено' : 'выключено'}
                      </div>
                    </div>
                    <div className="p-3 rounded-xl" style={{ background: 'var(--bg-secondary)' }}>
                      <div className="flex items-center gap-2 mb-1">
                        <WalletCards className="w-4 h-4" style={{ color: activeUser.has_payment_method ? 'var(--success)' : 'var(--text-tertiary)' }} />
                        <span className="text-sm" style={{ color: 'var(--text-primary)' }}>Карта</span>
                      </div>
                      <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                        {activeUser.has_payment_method ? 'сохранена' : 'нет'}
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 gap-2">
                    <Button
                      onClick={() => runAction('extend', () => api.extendAdminUserSubscription(activeUser.user_id, 30), 'Подписка продлена на 30 дней')}
                      loading={actionLoading === 'extend'}
                    >
                      <CalendarPlus className="w-5 h-5 mr-2" />
                      Продлить на 30 дней
                    </Button>
                    <Button
                      variant="secondary"
                      onClick={() => runAction('invite', () => api.sendAdminInvite(activeUser.user_id), 'Ссылка создана и отправлена, если пользователь принимает сообщения')}
                      loading={actionLoading === 'invite'}
                    >
                      <Send className="w-5 h-5 mr-2" />
                      Отправить ссылку в группу
                    </Button>
                    <Button
                      variant="secondary"
                      onClick={() => runAction(
                        'renewal',
                        () => api.updateAdminUserAutoRenewal(activeUser.user_id, !activeUser.auto_renewal),
                        activeUser.auto_renewal ? 'Автопродление отключено' : 'Автопродление включено'
                      )}
                      loading={actionLoading === 'renewal'}
                      disabled={!activeUser.has_payment_method && !activeUser.auto_renewal}
                    >
                      <RefreshCw className="w-5 h-5 mr-2" />
                      {activeUser.auto_renewal ? 'Отключить автопродление' : 'Включить автопродление'}
                    </Button>
                    <Button
                      variant="secondary"
                      onClick={() => {
                        if (window.confirm('Отвязать карту клиента?')) {
                          runAction('unlink', () => api.unlinkAdminUserCard(activeUser.user_id), 'Карта отвязана');
                        }
                      }}
                      loading={actionLoading === 'unlink'}
                      disabled={!activeUser.has_payment_method}
                    >
                      <XCircle className="w-5 h-5 mr-2" />
                      Отвязать карту
                    </Button>
                    <Button
                      variant="secondary"
                      onClick={() => {
                        if (window.confirm('Закрыть доступ клиента сейчас?')) {
                          runAction('revoke', () => api.revokeAdminUserSubscription(activeUser.user_id), 'Доступ закрыт, бот попытался убрать клиента из группы');
                        }
                      }}
                      loading={actionLoading === 'revoke'}
                    >
                      <Ban className="w-5 h-5 mr-2" />
                      Закрыть доступ
                    </Button>
                  </div>

                  <div>
                    <h3 className="font-semibold mb-2 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                      <CreditCard className="w-4 h-4" />
                      Последние платежи
                    </h3>
                    <div className="space-y-2">
                      {selectedUser!.payments.slice(0, 5).map((payment) => (
                        <div key={payment.payment_id} className="p-2 rounded-xl text-sm" style={{ background: 'var(--bg-secondary)' }}>
                          <div className="flex justify-between gap-2">
                            <span style={{ color: 'var(--text-primary)' }}>{formatMoney(payment.amount)}</span>
                            <span style={{ color: payment.status === 'succeeded' ? 'var(--success)' : 'var(--warning)' }}>{payment.status}</span>
                          </div>
                          <div className="text-xs truncate" style={{ color: 'var(--text-tertiary)' }}>{formatDate(payment.created_at)} · {payment.payment_id}</div>
                        </div>
                      ))}
                      {selectedUser!.payments.length === 0 && <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Платежей нет</p>}
                    </div>
                  </div>

                  <div>
                    <h3 className="font-semibold mb-2 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                      <AlertTriangle className="w-4 h-4" />
                      Отмены и тревоги
                    </h3>
                    <div className="space-y-2">
                      {selectedUser!.cancellations.slice(0, 3).map((item) => (
                        <div key={`${item.reason}-${item.created_at}`} className="p-2 rounded-xl text-sm" style={{ background: 'var(--bg-secondary)' }}>
                          <div style={{ color: 'var(--text-primary)' }}>{reasonLabel(item.reason)}</div>
                          <div className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{formatDate(item.created_at)}</div>
                        </div>
                      ))}
                      {selectedUser!.events.filter((event) => !event.resolved).slice(0, 3).map((event) => (
                        <div key={event.id} className="p-2 rounded-xl text-sm" style={{ background: 'var(--error-soft)' }}>
                          <div style={{ color: 'var(--error)' }}>{event.event_type}</div>
                          <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>{event.message}</div>
                        </div>
                      ))}
                      {selectedUser!.cancellations.length === 0 && selectedUser!.events.filter((event) => !event.resolved).length === 0 && (
                        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Нет отмен и открытых тревог</p>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-2 text-center">
                    <div className="p-2 rounded-xl" style={{ background: 'var(--bg-secondary)' }}>
                      <div className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{selectedUser!.activity.food_entries}</div>
                      <div className="text-xs" style={{ color: 'var(--text-tertiary)' }}>еда</div>
                    </div>
                    <div className="p-2 rounded-xl" style={{ background: 'var(--bg-secondary)' }}>
                      <div className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{selectedUser!.activity.sleep_entries}</div>
                      <div className="text-xs" style={{ color: 'var(--text-tertiary)' }}>сон</div>
                    </div>
                    <div className="p-2 rounded-xl" style={{ background: 'var(--bg-secondary)' }}>
                      <div className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{selectedUser!.activity.workout_entries}</div>
                      <div className="text-xs" style={{ color: 'var(--text-tertiary)' }}>тренировки</div>
                    </div>
                  </div>
                </div>
              )}
            </Panel>

            <Panel>
              <h3 className="font-semibold mb-2 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                <KeyRound className="w-4 h-4" />
                Быстрые состояния
              </h3>
              <div className="space-y-2 text-sm">
                <div className="flex items-center gap-2" style={{ color: 'var(--text-secondary)' }}>
                  <CheckCircle2 className="w-4 h-4" style={{ color: 'var(--success)' }} />
                  Активный клиент: можно отправить ссылку и продлить период.
                </div>
                <div className="flex items-center gap-2" style={{ color: 'var(--text-secondary)' }}>
                  <AlertTriangle className="w-4 h-4" style={{ color: 'var(--warning)' }} />
                  Pending старше 15 минут лучше проверять вручную.
                </div>
                <div className="flex items-center gap-2" style={{ color: 'var(--text-secondary)' }}>
                  <Link2 className="w-4 h-4" style={{ color: 'var(--accent)' }} />
                  Ссылка в группу создаётся одноразовой.
                </div>
              </div>
            </Panel>
          </aside>
        </div>
      </main>
    </div>
  );
}

export default AdminConsole;
