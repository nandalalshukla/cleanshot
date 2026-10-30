import { Pressable, StyleSheet } from 'react-native';

import { radius, spacing, useTheme } from '@/theme';

import { ThemedText } from './ThemedText';

export interface ChipProps {
  label: string;
  selected?: boolean;
  onPress?: () => void;
  detail?: string;
}

export function Chip({ label, selected, onPress, detail }: ChipProps) {
  const { colors } = useTheme();
  return (
    <Pressable
      accessibilityRole="checkbox"
      accessibilityState={{ checked: !!selected }}
      onPress={onPress}
      style={({ pressed }) => [
        styles.chip,
        {
          backgroundColor: selected ? colors.brand : colors.surface,
          borderColor: selected ? colors.brand : colors.border,
          opacity: pressed ? 0.8 : 1,
        },
      ]}
    >
      <ThemedText
        variant="caption"
        color={selected ? colors.onBrand : colors.text}
        style={styles.label}
      >
        {label}
      </ThemedText>
      {detail ? (
        <ThemedText variant="caption" color={selected ? colors.onBrand : colors.textMuted}>
          {detail}
        </ThemedText>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  chip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    borderWidth: 1,
    minHeight: 40,
    justifyContent: 'center',
  },
  label: { fontWeight: '600' },
});
