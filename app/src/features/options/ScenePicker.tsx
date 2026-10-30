import { useQuery } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { listScenes, scenePreviewPath } from '@/api/endpoints';
import type { ProcessOptions, SceneId } from '@/api/types';
import { Button, Chip, RemoteImage, TextField, ThemedText } from '@/components';
import { useApi } from '@/hooks/useApi';
import { radius, spacing, useTheme } from '@/theme';

interface Props {
  value: ProcessOptions;
  onChange: (patch: Partial<ProcessOptions>) => void;
}

export const randomSeed = () => Math.floor(Math.random() * 2_000_000_000);

/** Choose a generated scene, describe a custom one, and preview the backdrop. */
export function ScenePicker({ value, onChange }: Props) {
  const api = useApi();
  const { colors } = useTheme();
  const catalog = useQuery({
    queryKey: ['scenes', api.baseUrl],
    queryFn: () => listScenes(api),
    staleTime: Infinity,
  });

  // Debounce the free-text prompt so the preview isn't regenerated on every keystroke.
  const [draft, setDraft] = useState(value.scene_prompt ?? '');
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => () => clearTimeout(timer.current), []);
  const onPromptChange = (text: string) => {
    setDraft(text);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => onChange({ scene_prompt: text.trim() || null }), 700);
  };
  const prompt = value.scene_prompt;

  // The form pins a seed when scene mode is chosen, so the preview matches the exports.
  const seed = value.scene_seed ?? 0;
  const isCustom = value.scene === 'custom';
  const previewPath = scenePreviewPath(value.scene, {
    prompt: isCustom ? prompt : null,
    seed,
  });

  return (
    <View style={styles.stack}>
      {catalog.data?.backend === 'procedural' ? (
        <ThemedText variant="caption" muted>
          AI scenes aren&apos;t enabled on this server, so studio-style backdrops are used. Ask your
          admin to install the worker&apos;s diffusion extra for generated scenes.
        </ThemedText>
      ) : null}
      <View style={styles.wrap}>
        {(catalog.data?.scenes ?? []).map((s) => (
          <Chip
            key={s.id}
            label={s.label}
            selected={value.scene === s.id}
            onPress={() => onChange({ scene: s.id as SceneId })}
          />
        ))}
      </View>
      {isCustom ? (
        <TextField
          label="Describe the scene"
          placeholder="e.g. pink silk sheet with rose petals"
          value={draft}
          onChangeText={onPromptChange}
          autoCapitalize="sentences"
          maxLength={200}
        />
      ) : null}
      <RemoteImage
        key={previewPath}
        path={previewPath}
        style={[styles.preview, { borderColor: colors.border }]}
        contentFit="cover"
        accessibilityLabel="Scene preview"
      />
      <View style={styles.row}>
        <ThemedText variant="caption" muted style={styles.flex}>
          Every photo in the batch is placed in this scene.
        </ThemedText>
        <Button
          title="Shuffle"
          variant="secondary"
          onPress={() => onChange({ scene_seed: randomSeed() })}
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  stack: { gap: spacing.md },
  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  flex: { flex: 1 },
  preview: { width: '100%', aspectRatio: 1, borderRadius: radius.md, borderWidth: 1 },
});
