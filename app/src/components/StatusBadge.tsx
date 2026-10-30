import { StyleSheet, View } from 'react-native';

import type { BatchStatus, ImageStatus } from '@/api/types';
import { radius, spacing, useTheme, type ThemeColors } from '@/theme';

import { ThemedText } from './ThemedText';

type Status = ImageStatus | BatchStatus | 'flagged';

const LABELS: Record<Status, string> = {
  draft: 'Draft',
  uploaded: 'Uploaded',
  queued: 'Queued',
  processing: 'Processing',
  done: 'Done',
  completed: 'Completed',
  failed: 'Failed',
  cancelled: 'Cancelled',
  flagged: 'Check photo',
};

function tone(status: Status, c: ThemeColors): string {
  switch (status) {
    case 'done':
    case 'completed':
      return c.success;
    case 'failed':
      return c.danger;
    case 'flagged':
      return c.warning;
    case 'processing':
    case 'queued':
      return c.brand;
    default:
      return c.textMuted;
  }
}

export function StatusBadge({ status }: { status: Status }) {
  const { colors } = useTheme();
  const color = tone(status, colors);
  return (
    <View style={[styles.badge, { borderColor: color }]}>
      <ThemedText variant="caption" color={color} style={styles.text}>
        {LABELS[status]}
      </ThemedText>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    alignSelf: 'flex-start',
    borderWidth: 1,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  text: { fontSize: 11, fontWeight: '700' },
});
