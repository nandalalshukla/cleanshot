import { StyleSheet, View } from 'react-native';

import type { QualityReport } from '@/api/types';
import { Card, ThemedText } from '@/components';
import { radius, spacing, useTheme } from '@/theme';

export function QualityPanel({ report }: { report: QualityReport }) {
  const { colors } = useTheme();
  const tone =
    report.verdict === 'retake'
      ? colors.danger
      : report.verdict === 'warning'
        ? colors.warning
        : colors.success;
  const title =
    report.verdict === 'retake'
      ? 'Retake recommended'
      : report.verdict === 'warning'
        ? 'Worth a look'
        : 'Looks good';

  return (
    <Card style={{ borderColor: tone }}>
      <View style={styles.between}>
        <ThemedText variant="heading" color={tone}>
          {title}
        </ThemedText>
        <ThemedText variant="caption" muted accessibilityLabel={`Quality score ${report.score}`}>
          Score {report.score}/100
        </ThemedText>
      </View>
      {report.flags.length === 0 ? (
        <ThemedText muted>No problems found with this photo.</ThemedText>
      ) : (
        report.flags.map((f) => (
          <View key={f.code} style={styles.flag}>
            <View
              style={[
                styles.dot,
                { backgroundColor: f.severity === 'retake' ? colors.danger : colors.warning },
              ]}
            />
            <ThemedText style={styles.flex}>{f.message}</ThemedText>
          </View>
        ))
      )}
    </Card>
  );
}

const styles = StyleSheet.create({
  between: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  flag: { flexDirection: 'row', gap: spacing.sm, alignItems: 'flex-start' },
  dot: { width: 8, height: 8, borderRadius: radius.pill, marginTop: 7 },
  flex: { flex: 1 },
});
