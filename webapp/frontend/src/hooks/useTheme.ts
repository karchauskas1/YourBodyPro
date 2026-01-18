// Theme management hook

import { useEffect } from 'react';
import { useThemeStore, getEffectiveDarkMode } from '../store/useStore';
import type { ThemeMode, ColorScheme } from '../types';

export function useTheme() {
  const { themeMode, colorScheme, setThemeMode, setColorScheme } = useThemeStore();

  // Apply theme to document
  useEffect(() => {
    const isDark = getEffectiveDarkMode(themeMode);

    // Apply dark mode class
    if (isDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }

    // Apply color scheme
    document.documentElement.setAttribute('data-color-scheme', colorScheme);

    // Update body background for smooth transitions
    document.body.style.backgroundColor = 'var(--bg-primary)';
  }, [themeMode, colorScheme]);

  // Listen for system theme changes
  useEffect(() => {
    if (themeMode !== 'system') return;

    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

    const handleChange = () => {
      const isDark = mediaQuery.matches;
      if (isDark) {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
    };

    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, [themeMode]);

  return {
    themeMode,
    colorScheme,
    setThemeMode,
    setColorScheme,
    isDark: getEffectiveDarkMode(themeMode),
  };
}

export const themeOptions: { value: ThemeMode; label: string }[] = [
  { value: 'light', label: 'Светлая' },
  { value: 'dark', label: 'Тёмная' },
  { value: 'system', label: 'Системная' },
];

export const colorSchemeOptions: { value: ColorScheme; label: string; color: string }[] = [
  { value: 'peach', label: 'Персик', color: '#FF8A65' },
  { value: 'neutral', label: 'Нейтральная', color: '#6366F1' },
  { value: 'lavender', label: 'Лаванда', color: '#A855F7' },
];

export default useTheme;
