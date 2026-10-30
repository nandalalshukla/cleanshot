import { useMemo } from 'react';

import { ApiClient } from '@/api/client';
import { useSettings } from '@/lib/settings';

export function useApi(): ApiClient {
  const { settings } = useSettings();
  return useMemo(() => new ApiClient(settings), [settings]);
}
