import { Text, type TextProps } from 'react-native';

import { font, useTheme } from '@/theme';

type Variant = keyof typeof font;

export interface ThemedTextProps extends TextProps {
  variant?: Variant;
  muted?: boolean;
  color?: string;
}

export function ThemedText({ variant = 'body', muted, color, style, ...rest }: ThemedTextProps) {
  const { colors } = useTheme();
  return (
    <Text
      style={[font[variant], { color: color ?? (muted ? colors.textMuted : colors.text) }, style]}
      {...rest}
    />
  );
}
