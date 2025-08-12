import { create } from 'zustand';

type ThemeState = {
  mode: 'light' | 'dark';
  toggle: () => void;
};

export const useThemeStore = create<ThemeState>((set, get) => ({
  mode: (localStorage.getItem('theme-mode') as 'light' | 'dark') || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'),
  toggle: () => {
    const next = get().mode === 'light' ? 'dark' : 'light';
    localStorage.setItem('theme-mode', next);
    set({ mode: next });
    document.documentElement.classList.toggle('dark', next === 'dark');
  }
}));


