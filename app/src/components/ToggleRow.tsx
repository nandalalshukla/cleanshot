import { StyleSheet, Switch, View } from 'react-native';

import { spacing, useTheme } from '@/theme';

import { ThemedText } from './ThemedText';

export function ToggleRow({
  label,
  description,
  value,
  onChange,
}: {
  label: string;
  description?: string;
  value: boolean;
  onChange: (value: boolean) => void;
}) {
  const { colors } = useTheme();
  return (
    <View style={styles.row}>
      <View style={styles.text}>
        <ThemedText style={styles.label}>{label}</ThemedText>
        {description ? (
          <ThemedText variant="caption" muted>
            {description}
          </ThemedText>
        ) : null}
      </View>
      <Switch
        accessibilityLabel={label}
        value={value}
        onValueChange={onChange}
        trackColor={{ true: colors.brand, false: colors.border }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  text: { flex: 1, gap: 2 },
  label: { fontWeight: '600' },
});
