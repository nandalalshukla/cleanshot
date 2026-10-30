import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

import type { ProcessOptions } from '@/api/types';

export const DEFAULT_OPTIONS: ProcessOptions = {
  model: 'u2netp',
  refine_edges: true,
  presets: ['amazon'],
  custom_width: 2000,
  custom_height: 2000,
  fill: null,
  alignment: null,
  background_color: null,
  output_format: 'jpeg',
  shadow: 'ground',
  shadow_opacity: 0.35,
  auto_color: true,
  color_strength: 0.8,
};

const KEY = 'cleanshot.lastOptions.v1';

/** Remembers the seller's last-used options (brand colour, presets…) between batches. */
export function useSavedOptions() {
  const [options, setOptions] = useState<ProcessOptions>(DEFAULT_OPTIONS);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    AsyncStorage.getItem(KEY)
      .then((raw) => {
        if (raw)
          setOptions({ ...DEFAULT_OPTIONS, ...(JSON.parse(raw) as Partial<ProcessOptions>) });
      })
      .catch(() => undefined)
      .finally(() => setLoaded(true));
  }, []);

  const persist = useCallback((next: ProcessOptions) => {
    AsyncStorage.setItem(KEY, JSON.stringify(next)).catch(() => undefined);
  }, []);

  return { options, setOptions, loaded, persist };
}
