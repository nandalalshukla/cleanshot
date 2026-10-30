import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Alert, Pressable, StyleSheet, View, useWindowDimensions } from 'react-native';

import type { Batch, BatchImage } from '@/api/types';
import {
  Button,
  Card,
  EmptyState,
  ProgressBar,
  RemoteImage,
  Screen,
  Segmented,
  StatusBadge,
  ThemedText,
} from '@/components';
import { useBatch } from '@/features/batches/queries';
import { useBatchActions } from '@/features/batches/useBatchActions';
import { isFlagged, tileStatus } from '@/features/quality/quality';
import { radius, spacing, useTheme } from '@/theme';

export default function BatchScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const batch = useBatch(id);
  const actions = useBatchActions(id);
  const { colors } = useTheme();
  const [flaggedOnly, setFlaggedOnly] = useState(false);

  if (batch.isError) {
    return (
      <Screen>
        <EmptyState
          title="Batch not available"
          message={batch.error.message}
          action={<Button title="Back" variant="secondary" onPress={() => router.back()} />}
        />
      </Screen>
    );
  }
  if (!batch.data) return <Screen>{null}</Screen>;

  const b = batch.data;
  const done = b.counts.done ?? 0;
  const failed = b.counts.failed ?? 0;
  const processing = b.status === 'processing';

  const confirmDelete = () =>
    Alert.alert('Delete batch?', 'Photos and exports are removed from the server.', [
      { text: 'Keep', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: () => actions.remove.mutate(undefined, { onSuccess: () => router.back() }),
      },
    ]);

  return (
    <Screen
      refreshing={batch.isRefetching}
      onRefresh={() => void batch.refetch()}
      footer={
        <>
          <Button
            title={processing && done ? `Download ${done} ready (ZIP)` : 'Download ZIP'}
            disabled={!done}
            loading={actions.download.isPending}
            onPress={() => actions.download.mutate()}
          />
          {failed && !processing ? (
            <Button
              title={`Retry ${failed} failed`}
              variant="secondary"
              loading={actions.retryFailed.isPending}
              onPress={() => actions.retryFailed.mutate()}
            />
          ) : null}
        </>
      }
    >
      <Stack.Screen
        options={{
          title: b.name,
          headerRight: () => (
            <Pressable
              accessibilityRole="button"
              hitSlop={12}
              onPress={confirmDelete}
              style={{ paddingHorizontal: spacing.sm }}
            >
              <ThemedText color={colors.danger}>Delete</ThemedText>
            </Pressable>
          ),
        }}
      />

      <Card>
        <View style={styles.between}>
          <ThemedText variant="heading">
            {processing ? 'Processing…' : b.status === 'completed' ? 'All done' : 'Batch'}
          </ThemedText>
          <StatusBadge status={b.status} />
        </View>
        <ProgressBar value={b.progress} color={processing ? undefined : colors.success} />
        <ThemedText variant="caption" muted>
          {summary(b)}
        </ThemedText>
        {processing ? (
          <Button
            title="Stop remaining"
            variant="ghost"
            loading={actions.cancel.isPending}
            onPress={() => actions.cancel.mutate()}
          />
        ) : null}
      </Card>

      {b.needs_retake || b.warnings ? (
        <Card style={{ borderColor: b.needs_retake ? colors.danger : colors.warning }}>
          <ThemedText variant="heading">
            {b.needs_retake
              ? `${b.needs_retake} photo${b.needs_retake > 1 ? 's' : ''} should be retaken`
              : `${b.warnings} photo${b.warnings > 1 ? 's' : ''} worth a look`}
          </ThemedText>
          <ThemedText variant="caption" muted>
            Tap a flagged photo to see what went wrong and retake it — it re-processes
            automatically.
          </ThemedText>
          <Segmented<'all' | 'flagged'>
            value={flaggedOnly ? 'flagged' : 'all'}
            onChange={(v) => setFlaggedOnly(v === 'flagged')}
            options={[
              { value: 'all', label: `All (${b.total})` },
              { value: 'flagged', label: `Flagged (${b.needs_retake + b.warnings})` },
            ]}
          />
        </Card>
      ) : null}

      <PhotoGrid batch={b} images={flaggedOnly ? b.images.filter(isFlagged) : b.images} />
    </Screen>
  );
}

function summary(b: Batch): string {
  const parts = [`${b.counts.done ?? 0} of ${b.total} done`];
  if (b.counts.failed) parts.push(`${b.counts.failed} failed`);
  const waiting = (b.counts.queued ?? 0) + (b.counts.processing ?? 0);
  if (waiting) parts.push(`${waiting} in queue`);
  return parts.join(' · ');
}

function PhotoGrid({ batch, images }: { batch: Batch; images: BatchImage[] }) {
  const { width } = useWindowDimensions();
  const columns = width > 700 ? 4 : 2;
  const size = (Math.min(width, 900) - spacing.lg * 2 - spacing.md * (columns - 1)) / columns;
  return (
    <View style={styles.grid}>
      {images.map((img) => (
        <PhotoTile key={img.id} batchId={batch.id} image={img} size={size} />
      ))}
    </View>
  );
}

function PhotoTile({ batchId, image, size }: { batchId: string; image: BatchImage; size: number }) {
  const { colors } = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${image.filename}, ${image.status}`}
      onPress={() =>
        router.push({
          pathname: '/batch/[id]/[imageId]',
          params: { id: batchId, imageId: image.id },
        })
      }
      style={[
        styles.tile,
        { width: size, borderColor: colors.border, backgroundColor: colors.surface },
      ]}
    >
      <RemoteImage
        path={image.preview_url ?? image.original_url}
        style={{ width: size - 2, height: size - 2, borderRadius: radius.md }}
        contentFit={image.preview_url ? 'contain' : 'cover'}
      />
      <View style={styles.tileFooter}>
        <StatusBadge status={tileStatus(image)} />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  between: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.md },
  tile: { borderRadius: radius.md, borderWidth: StyleSheet.hairlineWidth, overflow: 'hidden' },
  tileFooter: { padding: spacing.sm, gap: spacing.xs },
});
