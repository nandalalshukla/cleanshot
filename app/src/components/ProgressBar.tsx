import { StyleSheet, View } from 'react-native';

import { radius, useTheme } from '@/theme';

export function ProgressBar({ value, color }: { value: number; color?: string }) {
  const { colors } = useTheme();
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100);
  return (
    <View
      accessibilityRole="progressbar"
      accessibilityValue={{ min: 0, max: 100, now: pct }}
      style={[styles.track, { backgroundColor: colors.surfaceMuted }]}
    >
      <View style={[styles.fill, { width: `${pct}%`, backgroundColor: color ?? colors.brand }]} />
    </View>
  );
}

const styles = StyleSheet.create({
  track: { height: 8, borderRadius: radius.pill, overflow: 'hidden' },
  fill: { height: '100%', borderRadius: radius.pill },
});
