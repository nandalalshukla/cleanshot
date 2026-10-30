import { router, Stack } from 'expo-router';
import { FlatList, Pressable, RefreshControl, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import type { BatchSummary } from '@/api/types';
import {
  Button,
  Card,
  EmptyState,
  ProgressBar,
  RemoteImage,
  StatusBadge,
  ThemedText,
} from '@/components';
import { useBatches } from '@/features/batches/queries';
import { radius, spacing, useTheme } from '@/theme';

export default function HomeScreen() {
  const { colors } = useTheme();
  const batches = useBatches();

  return (
    <SafeAreaView edges={['bottom']} style={[styles.flex, { backgroundColor: colors.background }]}>
      <Stack.Screen
        options={{
          headerRight: () => (
            <Pressable
              accessibilityRole="button"
              hitSlop={12}
              onPress={() => router.push('/settings')}
            >
              <ThemedText color={colors.brand}>Settings</ThemedText>
            </Pressable>
          ),
        }}
      />
      <FlatList
        data={batches.data ?? []}
        keyExtractor={(b) => b.id}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl
            refreshing={batches.isRefetching}
            onRefresh={() => void batches.refetch()}
          />
        }
        ListHeaderComponent={
          <Card>
            <ThemedText variant="title">Marketplace-ready photos</ThemedText>
            <ThemedText muted>
              Snap your products. CleanShot removes the background, centres them and exports Amazon,
              Flipkart, Meesho and Instagram sizes.
            </ThemedText>
          </Card>
        }
        ListEmptyComponent={
          batches.isError ? (
            <EmptyState
              title="Can't reach the server"
              message={batches.error.message}
              action={
                <Button
                  title="Open settings"
                  variant="secondary"
                  onPress={() => router.push('/settings')}
                />
              }
            />
          ) : batches.isPending ? undefined : (
            <EmptyState
              title="No batches yet"
              message="Start by picking up to 50 product photos from your gallery."
            />
          )
        }
        renderItem={({ item }) => <BatchRow batch={item} />}
      />
      <View
        style={[styles.footer, { borderTopColor: colors.border, backgroundColor: colors.surface }]}
      >
        <Button title="New batch" onPress={() => router.push('/batch/new')} />
      </View>
    </SafeAreaView>
  );
}

function BatchRow({ batch }: { batch: BatchSummary }) {
  const { colors } = useTheme();
  const done = batch.counts.done ?? 0;
  const failed = batch.counts.failed ?? 0;
  return (
    <Pressable
      accessibilityRole="button"
      onPress={() => router.push({ pathname: '/batch/[id]', params: { id: batch.id } })}
      style={({ pressed }) => ({ opacity: pressed ? 0.8 : 1 })}
    >
      <Card style={styles.row}>
        {batch.cover_url ? (
          <RemoteImage path={batch.cover_url} style={styles.cover} />
        ) : (
          <View style={[styles.cover, { backgroundColor: colors.surfaceMuted }]} />
        )}
        <View style={styles.rowBody}>
          <ThemedText variant="heading" numberOfLines={1}>
            {batch.name}
          </ThemedText>
          <ThemedText variant="caption" muted>
            {done}/{batch.total} done{failed ? ` · ${failed} failed` : ''}
            {batch.needs_retake ? ` · ${batch.needs_retake} to retake` : ''}
          </ThemedText>
          {batch.status === 'processing' ? <ProgressBar value={batch.progress} /> : null}
          <StatusBadge status={batch.status} />
        </View>
      </Card>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  list: { padding: spacing.lg, gap: spacing.md },
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  rowBody: { flex: 1, gap: spacing.xs },
  cover: { width: 72, height: 72, borderRadius: radius.md },
  footer: { padding: spacing.lg, borderTopWidth: StyleSheet.hairlineWidth },
});
