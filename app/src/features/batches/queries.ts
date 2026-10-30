import { useQuery } from '@tanstack/react-query';

import { getBatch, listBatches } from '@/api/endpoints';
import type { Batch } from '@/api/types';
import { useApi } from '@/hooks/useApi';

export const batchKeys = {
  all: (baseUrl: string) => ['batches', baseUrl] as const,
  detail: (baseUrl: string, id: string) => ['batches', baseUrl, id] as const,
};

/** Poll fast while the worker is busy, then stop. */
export function isActive(batch: Pick<Batch, 'status'> | undefined): boolean {
  return batch?.status === 'processing';
}

export function useBatches() {
  const api = useApi();
  return useQuery({
    queryKey: batchKeys.all(api.baseUrl),
    queryFn: () => listBatches(api),
    refetchInterval: (q) => (q.state.data?.some(isActive) ? 3_000 : false),
  });
}

export function useBatch(id: string) {
  const api = useApi();
  return useQuery({
    queryKey: batchKeys.detail(api.baseUrl, id),
    queryFn: () => getBatch(api, id),
    refetchInterval: (q) => (isActive(q.state.data) ? 1_500 : false),
  });
}
