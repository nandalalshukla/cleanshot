import { useQuery } from '@tanstack/react-query';
import { useState, type Dispatch, type SetStateAction } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { listPresets } from '@/api/endpoints';
import type {
  BackgroundMode,
  PresetId,
  ProcessOptions,
  SegmentationModel,
  ShadowStyle,
} from '@/api/types';
import { Card, Chip, Segmented, TextField, ThemedText, ToggleRow } from '@/components';
import { useApi } from '@/hooks/useApi';
import { radius, spacing, useTheme } from '@/theme';

import { randomSeed, ScenePicker } from './ScenePicker';

const BRAND_SWATCHES = [
  '#FFFFFF',
  '#F5F5F4',
  '#FDF2F8',
  '#EFF6FF',
  '#ECFDF5',
  '#FEF3C7',
  '#111827',
];
const HEX = /^#([0-9a-fA-F]{6})$/;

interface Props {
  value: ProcessOptions;
  /** A state setter: patches are applied to the latest options, never a stale snapshot. */
  onChange: Dispatch<SetStateAction<ProcessOptions>>;
}

export function OptionsForm({ value, onChange }: Props) {
  const api = useApi();
  const { colors } = useTheme();
  const [swatchPicks, setSwatchPicks] = useState(0);
  const presets = useQuery({ queryKey: ['presets', api.baseUrl], queryFn: () => listPresets(api) });
  const patch = (p: Partial<ProcessOptions>) => onChange((prev) => ({ ...prev, ...p }));
  const set = <K extends keyof ProcessOptions>(key: K, v: ProcessOptions[K]) =>
    patch({ [key]: v } as Partial<ProcessOptions>);

  const togglePreset = (id: PresetId) => {
    onChange((prev) => {
      const has = prev.presets.includes(id);
      const next = has ? prev.presets.filter((p) => p !== id) : [...prev.presets, id];
      return next.length ? { ...prev, presets: next } : prev; // keep at least one
    });
  };

  const background = value.background_color ?? '#FFFFFF';
  const needsWhite = (presets.data ?? []).some(
    (p) => p.white_background_required && value.presets.includes(p.id),
  );

  return (
    <View style={styles.stack}>
      <Card>
        <ThemedText variant="heading">Export for</ThemedText>
        <ThemedText variant="caption" muted>
          Pick one or more. Each photo is exported in every size you choose.
        </ThemedText>
        {presets.isError ? (
          <ThemedText color={colors.danger}>{presets.error.message}</ThemedText>
        ) : null}
        <View style={styles.wrap}>
          {(presets.data ?? []).map((p) => (
            <Chip
              key={p.id}
              label={p.label}
              detail={`${p.width}×${p.height}`}
              selected={value.presets.includes(p.id)}
              onPress={() => togglePreset(p.id)}
            />
          ))}
        </View>
        {value.presets.includes('custom') ? (
          <View style={styles.row}>
            <View style={styles.flex}>
              <NumberField
                label="Width (px)"
                value={value.custom_width}
                onCommit={(n) => set('custom_width', n)}
              />
            </View>
            <View style={styles.flex}>
              <NumberField
                label="Height (px)"
                value={value.custom_height}
                onCommit={(n) => set('custom_height', n)}
              />
            </View>
          </View>
        ) : null}
      </Card>

      <Card>
        <ThemedText variant="heading">Background</ThemedText>
        <Segmented<BackgroundMode>
          value={value.background_mode}
          onChange={(mode) =>
            onChange((prev) => ({
              ...prev,
              background_mode: mode,
              // Pin a seed so the preview the seller sees is exactly what gets exported.
              scene_seed: mode === 'scene' ? (prev.scene_seed ?? randomSeed()) : prev.scene_seed,
            }))
          }
          options={[
            { value: 'color', label: 'Solid colour' },
            { value: 'scene', label: 'AI scene' },
          ]}
        />
        {value.background_mode === 'scene' ? (
          <ScenePicker value={value} onChange={patch} />
        ) : (
          <>
            <View style={styles.wrap}>
              {BRAND_SWATCHES.map((hex) => (
                <Pressable
                  key={hex}
                  accessibilityRole="radio"
                  accessibilityLabel={`Background ${hex}`}
                  accessibilityState={{ selected: background === hex }}
                  onPress={() => {
                    setSwatchPicks((n) => n + 1); // resets the hex field to the picked colour
                    set('background_color', hex === '#FFFFFF' ? null : hex);
                  }}
                  style={[
                    styles.swatch,
                    {
                      backgroundColor: hex,
                      borderColor: background === hex ? colors.brand : colors.border,
                    },
                    background === hex && styles.swatchSelected,
                  ]}
                />
              ))}
            </View>
            <HexField
              key={swatchPicks}
              value={value.background_color}
              onCommit={(hex) => set('background_color', hex)}
            />
          </>
        )}
        {needsWhite &&
        (value.background_mode === 'scene' ||
          (value.background_color && value.background_color !== '#FFFFFF')) ? (
          <ThemedText variant="caption" color={colors.warning}>
            Amazon, Flipkart and Meesho main images should use a pure white background. Use scenes
            for Instagram and extra listing photos.
          </ThemedText>
        ) : null}
      </Card>

      <Card>
        <ThemedText variant="heading">Look</ThemedText>
        <ToggleRow
          label="Auto colour correction"
          description="Fixes yellow indoor light, dull colours and dark photos."
          value={value.auto_color}
          onChange={(v) => set('auto_color', v)}
        />
        {value.auto_color ? (
          <Segmented<number>
            value={value.color_strength}
            onChange={(v) => set('color_strength', v)}
            options={[
              { value: 0.5, label: 'Subtle' },
              { value: 0.8, label: 'Natural' },
              { value: 1, label: 'Strong' },
            ]}
          />
        ) : null}
        <ThemedText variant="caption" muted>
          Shadow
        </ThemedText>
        <Segmented<ShadowStyle>
          value={value.shadow}
          onChange={(v) => set('shadow', v)}
          options={[
            { value: 'ground', label: 'Soft' },
            { value: 'drop', label: 'Drop' },
            { value: 'none', label: 'None' },
          ]}
        />
        <ThemedText variant="caption" muted>
          Product size in frame
        </ThemedText>
        <Segmented<number>
          value={value.fill ?? 0}
          onChange={(v) => set('fill', v === 0 ? null : v)}
          options={[
            { value: 0, label: 'Auto' },
            { value: 0.75, label: '75%' },
            { value: 0.85, label: '85%' },
            { value: 0.95, label: '95%' },
          ]}
        />
        <ThemedText variant="caption" muted>
          Edge quality
        </ThemedText>
        <Segmented<SegmentationModel>
          value={value.model}
          onChange={(v) => set('model', v)}
          options={[
            { value: 'u2netp', label: 'Fast' },
            { value: 'isnet-general-use', label: 'Quality' },
            { value: 'birefnet-general-lite', label: 'Best' },
          ]}
        />
        <ThemedText variant="caption" muted>
          {value.model === 'u2netp'
            ? 'Fast works well for boxes, bottles and solid products.'
            : 'Slower, but cleaner edges on fabric, hair and jewellery.'}
        </ThemedText>
        <ThemedText variant="caption" muted>
          File format
        </ThemedText>
        <Segmented
          value={value.output_format}
          onChange={(v) => set('output_format', v)}
          options={[
            { value: 'jpeg', label: 'JPG' },
            { value: 'png', label: 'PNG' },
            { value: 'webp', label: 'WebP' },
          ]}
        />
      </Card>
    </View>
  );
}

/** Keeps a local draft while typing and commits a clamped value on blur. */
function NumberField({
  label,
  value,
  onCommit,
  min = 256,
  max = 4096,
}: {
  label: string;
  value: number;
  onCommit: (n: number) => void;
  min?: number;
  max?: number;
}) {
  const [draft, setDraft] = useState(String(value));
  const commit = () => {
    const n = parseInt(draft, 10);
    const clamped = Number.isNaN(n) ? value : Math.min(max, Math.max(min, n));
    setDraft(String(clamped));
    onCommit(clamped);
  };
  return (
    <TextField
      label={label}
      keyboardType="number-pad"
      value={draft}
      onChangeText={(t) => setDraft(t.replace(/\D/g, ''))}
      onBlur={commit}
      onSubmitEditing={commit}
      hint={`${min}–${max}`}
    />
  );
}

function HexField({
  value,
  onCommit,
}: {
  value: string | null;
  onCommit: (hex: string | null) => void;
}) {
  const [draft, setDraft] = useState(value ?? '');
  const valid = draft === '' || HEX.test(normalizeHex(draft));
  return (
    <TextField
      label="Brand colour (hex)"
      placeholder="#FFFFFF"
      value={draft}
      autoCapitalize="characters"
      maxLength={7}
      onChangeText={(t) => {
        setDraft(t);
        const hex = normalizeHex(t);
        if (t === '') onCommit(null);
        else if (HEX.test(hex)) onCommit(hex === '#FFFFFF' ? null : hex);
      }}
      hint={valid ? undefined : 'Use 6 hex digits, e.g. #F5E6D3'}
    />
  );
}

function normalizeHex(t: string): string {
  const v = t.trim().toUpperCase();
  return v.startsWith('#') ? v : `#${v}`;
}

const styles = StyleSheet.create({
  stack: { gap: spacing.lg },
  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  row: { flexDirection: 'row', gap: spacing.md },
  flex: { flex: 1 },
  swatch: { width: 40, height: 40, borderRadius: radius.pill, borderWidth: 1 },
  swatchSelected: { borderWidth: 3 },
});
