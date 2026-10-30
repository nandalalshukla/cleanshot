import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Alert, StyleSheet, View } from 'react-native';

import {
  Button,
  Card,
  RemoteImage,
  Screen,
  Segmented,
  StatusBadge,
  ThemedText,
} from '@/components';
import { useBatch } from '@/features/batches/queries';
import { useBatchActions } from '@/features/batches/useBatchActions';
import { QualityPanel } from '@/features/quality/QualityPanel';
import { pickFromLibrary, takePhoto, type PickedPhoto } from '@/features/photos/pickPhotos';
import { presetLabel } from '@/lib/format';
import { radius, spacing, useTheme } from '@/theme';

type View_ = 'after' | 'before';

export default function PhotoScreen() {
  const { id, imageId } = useLocalSearchParams<{ id: string; imageId: string }>();
  const batch = useBatch(id);
  const actions = useBatchActions(id);
  const { colors } = useTheme();
  const [view, setView] = useState<View_>('after');

  const image = batch.data?.images.find((i) => i.id === imageId);
  if (!batch.data) return <Screen>{null}</Screen>;
  if (!image) {
    return (
      <Screen>
        <ThemedText muted>This photo was removed.</ThemedText>
      </Screen>
    );
  }

  const isDone = image.status === 'done';
  const busy = image.status === 'queued' || image.status === 'processing';
  const canRetake = !busy && batch.data.status !== 'cancelled';
  const shown = view === 'after' && image.preview_url ? image.preview_url : image.original_url;

  const replace = async (source: 'camera' | 'library') => {
    let photo: PickedPhoto | null | undefined;
    try {
      photo = source === 'camera' ? await takePhoto() : (await pickFromLibrary(1))[0];
    } catch (err) {
      Alert.alert('Camera unavailable', (err as Error).message);
      return;
    }
    if (photo) actions.replaceImage.mutate({ imageId: image.id, photo });
  };

  const confirmRemove = () =>
    Alert.alert('Remove photo?', 'It will be left out of the ZIP.', [
      { text: 'Keep', style: 'cancel' },
      {
        text: 'Remove',
        style: 'destructive',
        onPress: () => actions.deleteImage.mutate(image.id, { onSuccess: () => router.back() }),
      },
    ]);

  return (
    <Screen>
      <Stack.Screen options={{ title: image.filename }} />

      <Card>
        <View style={styles.between}>
          <StatusBadge status={image.status} />
          {isDone ? (
            <Segmented<View_>
              value={view}
              onChange={setView}
              options={[
                { value: 'before', label: 'Before' },
                { value: 'after', label: 'After' },
              ]}
            />
          ) : null}
        </View>
        <RemoteImage
          path={view === 'before' ? `${image.original_url}?full=true` : shown}
          style={[styles.hero, { borderColor: colors.border }]}
          accessibilityLabel={view === 'before' ? 'Original photo' : 'Processed photo'}
        />
        {image.error ? <ThemedText color={colors.danger}>{image.error}</ThemedText> : null}
        {busy ? <ThemedText muted>Processing — this updates automatically.</ThemedText> : null}
      </Card>

      {image.quality ? <QualityPanel report={image.quality} /> : null}

      {isDone && image.outputs.length ? (
        <Card>
          <ThemedText variant="heading">Exports</ThemedText>
          {image.outputs.map((o) => (
            <View key={o.preset} style={styles.between}>
              <View>
                <ThemedText>{presetLabel(o.preset)}</ThemedText>
                <ThemedText variant="caption" muted>
                  {o.width}×{o.height}
                </ThemedText>
              </View>
              <Button
                title="Share"
                variant="secondary"
                loading={
                  actions.shareOutput.isPending && actions.shareOutput.variables?.url === o.url
                }
                onPress={() => actions.shareOutput.mutate({ url: o.url, filename: o.filename })}
              />
            </View>
          ))}
        </Card>
      ) : null}

      <Card>
        <ThemedText variant="heading">Not happy with it?</ThemedText>
        <ThemedText variant="caption" muted>
          Retake the photo with the whole product in frame on a plain surface.
        </ThemedText>
        <View style={styles.row}>
          <Button
            title="Retake"
            style={styles.flex}
            disabled={!canRetake}
            loading={actions.replaceImage.isPending}
            onPress={() => replace('camera')}
          />
          <Button
            title="Replace"
            variant="secondary"
            style={styles.flex}
            disabled={!canRetake || actions.replaceImage.isPending}
            onPress={() => replace('library')}
          />
        </View>
        {image.status === 'failed' || image.status === 'cancelled' ? (
          <Button
            title="Try again"
            variant="secondary"
            loading={actions.retryImage.isPending}
            onPress={() => actions.retryImage.mutate(image.id)}
          />
        ) : null}
        <Button title="Remove from batch" variant="ghost" disabled={busy} onPress={confirmRemove} />
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  between: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: spacing.md,
  },
  row: { flexDirection: 'row', gap: spacing.md },
  flex: { flex: 1 },
  hero: {
    width: '100%',
    aspectRatio: 1,
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
  },
});
