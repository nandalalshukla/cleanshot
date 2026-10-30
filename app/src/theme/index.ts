import { useColorScheme } from 'react-native';

const palette = {
  brand: '#2563EB',
  brandPressed: '#1D4ED8',
  success: '#16A34A',
  warning: '#D97706',
  danger: '#DC2626',
};

export const lightColors = {
  ...palette,
  background: '#F8FAFC',
  surface: '#FFFFFF',
  surfaceMuted: '#F1F5F9',
  border: '#E2E8F0',
  text: '#0F172A',
  textMuted: '#64748B',
  onBrand: '#FFFFFF',
};

export type ThemeColors = typeof lightColors;

export const darkColors: ThemeColors = {
  ...palette,
  background: '#0B1120',
  surface: '#111827',
  surfaceMuted: '#1F2937',
  border: '#1F2937',
  text: '#F1F5F9',
  textMuted: '#94A3B8',
  onBrand: '#FFFFFF',
};

export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 } as const;
export const radius = { sm: 8, md: 12, lg: 16, pill: 999 } as const;
export const font = {
  title: { fontSize: 24, fontWeight: '700' },
  heading: { fontSize: 18, fontWeight: '600' },
  body: { fontSize: 15, fontWeight: '400' },
  caption: { fontSize: 13, fontWeight: '400' },
} as const;

export function useTheme() {
  const scheme = useColorScheme();
  return { colors: scheme === 'dark' ? darkColors : lightColors, dark: scheme === 'dark' };
}
