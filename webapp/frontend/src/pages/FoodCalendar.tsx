// Food Calendar page - view food history by day

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { format, startOfMonth, endOfMonth, eachDayOfInterval, getDay, isSameDay, isToday } from 'date-fns';
import { ru } from 'date-fns/locale';
import { Layout, Card, LoadingSpinner } from '../components/Layout';
import { api } from '../api/client';
import type { FoodEntry } from '../types';
import { useTelegram } from '../hooks/useTelegram';
import { ArrowLeft, ChevronLeft, ChevronRight, X } from 'lucide-react';

interface DayData {
  count: number;
  entries: FoodEntry[];
}

export function FoodCalendar() {
  const navigate = useNavigate();
  const { haptic } = useTelegram();

  const [currentDate, setCurrentDate] = useState(new Date());
  const [calendarData, setCalendarData] = useState<Record<string, DayData>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [selectedDay, setSelectedDay] = useState<string | null>(null);

  useEffect(() => {
    loadCalendarData();
  }, [currentDate]);

  const loadCalendarData = async () => {
    try {
      setIsLoading(true);
      const year = currentDate.getFullYear();
      const month = currentDate.getMonth() + 1;

      const response = await api.getFoodCalendar(year, month);
      setCalendarData(response.days);
    } catch (err) {
      console.error('Failed to load calendar:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handlePrevMonth = () => {
    haptic('light');
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() - 1, 1));
  };

  const handleNextMonth = () => {
    haptic('light');
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 1));
  };

  const handleDayClick = (dateStr: string) => {
    haptic('selection');
    if (calendarData[dateStr]) {
      setSelectedDay(dateStr);
    }
  };

  // Generate calendar days
  const monthStart = startOfMonth(currentDate);
  const monthEnd = endOfMonth(currentDate);
  const daysInMonth = eachDayOfInterval({ start: monthStart, end: monthEnd });

  // Get the day of week for the first day (0 = Sunday, 1 = Monday, etc.)
  // Adjust to start from Monday (0 = Monday, 6 = Sunday)
  const startDayOfWeek = getDay(monthStart);
  const adjustedStartDay = startDayOfWeek === 0 ? 6 : startDayOfWeek - 1;

  // Week day headers (starting from Monday)
  const weekDays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

  // Get color based on entry count
  const getDayColor = (count: number): string => {
    if (count >= 4) return 'var(--success)';
    if (count >= 2) return 'var(--warning)';
    if (count >= 1) return 'var(--accent)';
    return 'transparent';
  };

  return (
    <Layout>
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => navigate(-1)}
          className="p-2 rounded-xl transition-colors"
          style={{ background: 'var(--bg-glass)' }}
        >
          <ArrowLeft className="w-5 h-5" style={{ color: 'var(--text-primary)' }} />
        </button>
        <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
          Календарь питания
        </h1>
      </div>

      {/* Month navigation */}
      <Card className="mb-4">
        <div className="flex items-center justify-between">
          <button
            onClick={handlePrevMonth}
            className="p-2 rounded-xl transition-colors"
            style={{ background: 'var(--bg-secondary)' }}
          >
            <ChevronLeft className="w-5 h-5" style={{ color: 'var(--text-primary)' }} />
          </button>
          <h2 className="text-lg font-semibold capitalize" style={{ color: 'var(--text-primary)' }}>
            {format(currentDate, 'LLLL yyyy', { locale: ru })}
          </h2>
          <button
            onClick={handleNextMonth}
            className="p-2 rounded-xl transition-colors"
            style={{ background: 'var(--bg-secondary)' }}
          >
            <ChevronRight className="w-5 h-5" style={{ color: 'var(--text-primary)' }} />
          </button>
        </div>
      </Card>

      {/* Calendar */}
      <Card>
        {isLoading ? (
          <div className="flex justify-center py-8">
            <LoadingSpinner />
          </div>
        ) : (
          <>
            {/* Week day headers */}
            <div className="grid grid-cols-7 gap-1 mb-2">
              {weekDays.map((day) => (
                <div
                  key={day}
                  className="text-center text-xs font-medium py-2"
                  style={{ color: 'var(--text-tertiary)' }}
                >
                  {day}
                </div>
              ))}
            </div>

            {/* Calendar grid */}
            <div className="grid grid-cols-7 gap-1">
              {/* Empty cells for days before month start */}
              {Array.from({ length: adjustedStartDay }).map((_, i) => (
                <div key={`empty-${i}`} className="aspect-square" />
              ))}

              {/* Days of the month */}
              {daysInMonth.map((day) => {
                const dateStr = format(day, 'yyyy-MM-dd');
                const dayData = calendarData[dateStr];
                const hasData = dayData && dayData.count > 0;
                const isCurrentDay = isToday(day);

                return (
                  <button
                    key={dateStr}
                    onClick={() => handleDayClick(dateStr)}
                    className={`aspect-square rounded-xl flex flex-col items-center justify-center transition-all ${
                      hasData ? 'cursor-pointer' : 'cursor-default'
                    }`}
                    style={{
                      background: hasData ? getDayColor(dayData.count) + '20' : 'transparent',
                      border: isCurrentDay ? `2px solid var(--accent)` : '2px solid transparent',
                    }}
                  >
                    <span
                      className="text-sm font-medium"
                      style={{
                        color: hasData ? 'var(--text-primary)' : 'var(--text-tertiary)',
                      }}
                    >
                      {format(day, 'd')}
                    </span>
                    {hasData && (
                      <div
                        className="w-1.5 h-1.5 rounded-full mt-0.5"
                        style={{ background: getDayColor(dayData.count) }}
                      />
                    )}
                  </button>
                );
              })}
            </div>

            {/* Legend */}
            <div className="flex items-center justify-center gap-4 mt-4 pt-4 border-t" style={{ borderColor: 'var(--border)' }}>
              <div className="flex items-center gap-1">
                <div className="w-2 h-2 rounded-full" style={{ background: 'var(--accent)' }} />
                <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>1</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-2 h-2 rounded-full" style={{ background: 'var(--warning)' }} />
                <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>2-3</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-2 h-2 rounded-full" style={{ background: 'var(--success)' }} />
                <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>4+</span>
              </div>
            </div>
          </>
        )}
      </Card>

      {/* Day detail modal */}
      {selectedDay && calendarData[selectedDay] && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center"
          style={{ background: 'rgba(0, 0, 0, 0.5)' }}
          onClick={() => setSelectedDay(null)}
        >
          <div
            className="w-full max-w-lg rounded-t-3xl p-6 animate-in slide-up"
            style={{ background: 'var(--bg-primary)', maxHeight: '70vh', overflowY: 'auto' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
                {format(new Date(selectedDay), 'd MMMM yyyy', { locale: ru })}
              </h3>
              <button
                onClick={() => setSelectedDay(null)}
                className="p-2 rounded-xl"
                style={{ background: 'var(--bg-glass)' }}
              >
                <X className="w-5 h-5" style={{ color: 'var(--text-primary)' }} />
              </button>
            </div>

            <div className="space-y-3">
              {calendarData[selectedDay].entries.map((entry, index) => (
                <div
                  key={entry.id || index}
                  className="p-3 rounded-xl"
                  style={{ background: 'var(--bg-secondary)' }}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                        {entry.description}
                      </p>
                      <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>
                        {entry.time}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}

export default FoodCalendar;
