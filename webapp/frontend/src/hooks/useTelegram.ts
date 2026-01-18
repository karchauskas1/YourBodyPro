// Hook for Telegram WebApp integration

import { useEffect, useCallback } from 'react';
import { useStore } from '../store/useStore';
import type { TelegramWebApp } from '../types';

export function useTelegram() {
  const { setDarkMode, setUser } = useStore();

  const tg: TelegramWebApp | undefined = window.Telegram?.WebApp;

  // Initialize Telegram WebApp
  useEffect(() => {
    if (!tg) return;

    // Tell Telegram we're ready
    tg.ready();

    // Expand to full height
    tg.expand();

    // Set theme based on Telegram color scheme
    const isDark = tg.colorScheme === 'dark';
    setDarkMode(isDark);

    // Apply dark class to document
    if (isDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }

    // Set user from initDataUnsafe
    if (tg.initDataUnsafe?.user) {
      setUser({
        user_id: tg.initDataUnsafe.user.id,
        username: tg.initDataUnsafe.user.username,
        first_name: tg.initDataUnsafe.user.first_name,
        last_name: tg.initDataUnsafe.user.last_name,
        language_code: tg.initDataUnsafe.user.language_code,
      });
    }

    // Listen for theme changes
    const handleThemeChange = () => {
      const newIsDark = tg.colorScheme === 'dark';
      setDarkMode(newIsDark);
      if (newIsDark) {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
    };

    tg.onEvent('themeChanged', handleThemeChange);

    return () => {
      tg.offEvent('themeChanged', handleThemeChange);
    };
  }, [tg, setDarkMode, setUser]);

  // Haptic feedback
  const haptic = useCallback(
    (type: 'light' | 'medium' | 'heavy' | 'success' | 'warning' | 'error' | 'selection') => {
      if (!tg?.HapticFeedback) return;

      switch (type) {
        case 'light':
        case 'medium':
        case 'heavy':
          tg.HapticFeedback.impactOccurred(type);
          break;
        case 'success':
        case 'warning':
        case 'error':
          tg.HapticFeedback.notificationOccurred(type);
          break;
        case 'selection':
          tg.HapticFeedback.selectionChanged();
          break;
      }
    },
    [tg]
  );

  // Main button controls
  const mainButton = {
    show: useCallback(
      (text: string, onClick: () => void) => {
        if (!tg?.MainButton) return;
        tg.MainButton.setText(text);
        tg.MainButton.onClick(onClick);
        tg.MainButton.show();
      },
      [tg]
    ),
    hide: useCallback(() => {
      tg?.MainButton?.hide();
    }, [tg]),
    showProgress: useCallback(() => {
      tg?.MainButton?.showProgress();
    }, [tg]),
    hideProgress: useCallback(() => {
      tg?.MainButton?.hideProgress();
    }, [tg]),
    enable: useCallback(() => {
      tg?.MainButton?.enable();
    }, [tg]),
    disable: useCallback(() => {
      tg?.MainButton?.disable();
    }, [tg]),
  };

  // Back button controls
  const backButton = {
    show: useCallback(
      (onClick: () => void) => {
        if (!tg?.BackButton) return;
        tg.BackButton.onClick(onClick);
        tg.BackButton.show();
      },
      [tg]
    ),
    hide: useCallback(() => {
      tg?.BackButton?.hide();
    }, [tg]),
  };

  // Popups
  const showAlert = useCallback(
    (message: string): Promise<void> => {
      return new Promise((resolve) => {
        if (tg?.showAlert) {
          tg.showAlert(message, resolve);
        } else {
          alert(message);
          resolve();
        }
      });
    },
    [tg]
  );

  const showConfirm = useCallback(
    (message: string): Promise<boolean> => {
      return new Promise((resolve) => {
        if (tg?.showConfirm) {
          tg.showConfirm(message, resolve);
        } else {
          resolve(confirm(message));
        }
      });
    },
    [tg]
  );

  // Close app
  const close = useCallback(() => {
    tg?.close();
  }, [tg]);

  // Open link
  const openLink = useCallback(
    (url: string) => {
      if (tg?.openLink) {
        tg.openLink(url);
      } else {
        window.open(url, '_blank');
      }
    },
    [tg]
  );

  return {
    tg,
    isAvailable: !!tg,
    initData: tg?.initData || '',
    user: tg?.initDataUnsafe?.user,
    colorScheme: tg?.colorScheme || 'light',
    themeParams: tg?.themeParams || {},
    haptic,
    mainButton,
    backButton,
    showAlert,
    showConfirm,
    close,
    openLink,
  };
}

export default useTelegram;
