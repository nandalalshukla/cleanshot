import { router, Stack } from 'expo-router';
import { useState } from 'react';
import { Alert, Pressable, StyleSheet, View } from 'react-native';
import { Image } from 'expo-image';

import { Button, Card, ProgressBar, Screen, TextField, ThemedText } from '@/components';
import { useCreateBatch } from '@/features/batches/useCreateBatch';
import { OptionsForm } from '@/features/options/OptionsForm';
import { useSavedOptions } from '@/features/options/defaults';
import {
  MAX_PHOTOS_PER_BATCH,
  pickFromLibrary,
  takePhoto,
  type PickedPhoto,
} from '@/features/photos/pickPhotos';
import { radius, spacing, useTheme } from '@/theme';

export default function NewBatchScreen() {
  const { colors } = useTheme();
  const [photos, setPhotos] = useState<PickedPhoto[]>([]);
  const [name, setName] = useState('');
  const { options, setOptions, persist } = useSavedOptions();
  const { state, run, cancel } = useCreateBatch();
  const busy = ['creating', 'uploading', 'starting'].includes(state.phase);
  const remaining = MAX_PHOTOS_PER_BATCH - photos.length;

  const addFromLibrary = async () => {
    const picked = await pickFromLibrary(remaining);
    setPhotos((prev) => dedupe([...prev, ...picked]).slice(0, MAX_PHOTOS_PER_BATCH));
  };

  const addFromCamera = async () => {
    try {
      const photo = await takePhoto();
      if (photo) setPhotos((prev) => [...prev, photo].slice(0, MAX_PHOTOS_PER_BATCH));
    } catch (err) {
      Alert.alert('Camera unavailable', (err as Error).message);
    }
  };

  const submit = async () => {
    persist(options);
    const batch = await run(photos, options, name.trim() || undefined);
    if (batch) router.replace({ pathname: '/batch/[id]', params: { id: batch.id } });
  };

  const uploadProgress = state.total ? state.uploaded / state.total : 0;

  return (
    <Screen
      footer={
        busy ? (
          <View style={styles.footerStack}>
            <ThemedText variant="caption" muted>
              {state.phase === 'creating'
                ? 'Creating batch…'
                : state.phase === 'starting'
                  ? 'Starting…'
                  : `Uploading ${state.uploaded}/${state.total}`}
            </ThemedText>
            <ProgressBar value={uploadProgress} />
            <Button title="Cancel upload" variant="ghost" onPress={cancel} />
          </View>
        ) : (
          <Button
            title={
              photos.length
                ? `Process ${photos.length} photo${photos.length > 1 ? 's' : ''}`
                : 'Add photos to start'
            }
            disabled={!photos.length}
            onPress={submit}
          />
        )
      }
    >
      <Stack.Screen
        options={{ title: 'New batch', headerBackVisible: !busy, gestureEnabled: !busy }}
      />

      {state.phase === 'error' ? (
        <Card style={{ borderColor: colors.danger }}>
          <ThemedText color={colors.danger}>{state.error}</ThemedText>
        </Card>
      ) : null}
      {state.rejected.length ? (
        <Card style={{ borderColor: colors.warning }}>
          <ThemedText color={colors.warning}>
            {state.rejected.length} photo(s) were skipped:{' '}
            {state.rejected.map((r) => r.name).join(', ')}
          </ThemedText>
        </Card>
      ) : null}

      <Card>
        <View style={styles.headerRow}>
          <ThemedText variant="heading">Photos</ThemedText>
          <ThemedText variant="caption" muted>
            {photos.length}/{MAX_PHOTOS_PER_BATCH}
          </ThemedText>
        </View>
        {photos.length ? (
          <View style={styles.grid}>
            {photos.map((p) => (
              <Pressable
                key={p.uri}
                accessibilityRole="button"
                accessibilityLabel={`Remove ${p.name}`}
                disabled={busy}
                onPress={() => setPhotos((prev) => prev.filter((x) => x.uri !== p.uri))}
              >
                <Image source={{ uri: p.uri }} style={styles.thumb} contentFit="cover" />
                <View style={[styles.remove, { backgroundColor: colors.text }]}>
                  <ThemedText variant="caption" color={colors.background}>
                    ✕
                  </ThemedText>
                </View>
              </Pressable>
            ))}
          </View>
        ) : (
          <ThemedText muted>
            Tip: shoot on a plain table in daylight, with the whole product in frame.
          </ThemedText>
        )}
        <View style={styles.row}>
          <Button
            title="Gallery"
            variant="secondary"
            style={styles.flex}
            disabled={busy || remaining <= 0}
            onPress={addFromLibrary}
          />
          <Button
            title="Camera"
            variant="secondary"
            style={styles.flex}
            disabled={busy || remaining <= 0}
            onPress={addFromCamera}
          />
        </View>
      </Card>

      <Card>
        <TextField
          label="Batch name (optional)"
          placeholder="e.g. Diwali kurtis"
          value={name}
          onChangeText={setName}
          autoCapitalize="sentences"
          maxLength={80}
        />
      </Card>

      <OptionsForm value={options} onChange={setOptions} />
    </Screen>
  );
}

function dedupe(photos: PickedPhoto[]): PickedPhoto[] {
  const seen = new Set<string>();
  return photos.filter((p) => (seen.has(p.uri) ? false : (seen.add(p.uri), true)));
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  row: { flexDirection: 'row', gap: spacing.md },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  thumb: { width: 76, height: 76, borderRadius: radius.sm },
  remove: {
    position: 'absolute',
    top: 4,
    right: 4,
    width: 20,
    height: 20,
    borderRadius: radius.pill,
    alignItems: 'center',
    justifyContent: 'center',
    opacity: 0.8,
  },
  footerStack: { gap: spacing.sm },
});
