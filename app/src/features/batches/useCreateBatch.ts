import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useRef, useState } from 'react';

import { createBatch, deleteBatch, startBatch, uploadPhoto } from '@/api/endpoints';
import type { Batch, ProcessOptions } from '@/api/types';
import { prepareForUpload, type PickedPhoto } from '@/features/photos/pickPhotos';
import { useApi } from '@/hooks/useApi';

import { batchKeys } from './queries';

export type UploadPhase = 'idle' | 'creating' | 'uploading' | 'starting' | 'done' | 'error';

export interface UploadState {
  phase: UploadPhase;
  uploaded: number;
  total: number;
  error?: string;
  /** Photos the server rejected (e.g. not an image); the rest still go through. */
  rejected: { name: string; reason: string }[];
}

const UPLOAD_CONCURRENCY = 3;
const initial: UploadState = { phase: 'idle', uploaded: 0, total: 0, rejected: [] };

/**
 * create batch → upload every photo (a few at a time) → start processing.
 * Per-photo failures don't abort the batch; they are reported in `rejected`.
 */
export function useCreateBatch() {
  const api = useApi();
  const queryClient = useQueryClient();
  const [state, setState] = useState<UploadState>(initial);
  const cancelled = useRef(false);

  const run = useCallback(
    async (
      photos: PickedPhoto[],
      options: ProcessOptions,
      name?: string,
    ): Promise<Batch | null> => {
      cancelled.current = false;
      setState({ ...initial, phase: 'creating', total: photos.length });
      let batch: Batch | null = null;
      try {
        batch = await createBatch(api, options, name);
        setState((s) => ({ ...s, phase: 'uploading' }));

        const queue = photos.map((p, i) => ({ p, i }));
        const rejected: UploadState['rejected'] = [];
        const worker = async () => {
          for (let next = queue.shift(); next; next = queue.shift()) {
            if (cancelled.current) return;
            try {
              await uploadPhoto(api, batch!.id, await prepareForUpload(next.p), next.i);
            } catch (err) {
              rejected.push({ name: next.p.name, reason: (err as Error).message });
            }
            setState((s) => ({ ...s, uploaded: s.uploaded + 1, rejected: [...rejected] }));
          }
        };
        await Promise.all(Array.from({ length: UPLOAD_CONCURRENCY }, worker));
        if (cancelled.current) {
          await deleteBatch(api, batch.id).catch(() => undefined);
          setState(initial);
          return null;
        }
        if (rejected.length === photos.length) {
          throw new Error(rejected[0]?.reason ?? 'No photos could be uploaded.');
        }

        setState((s) => ({ ...s, phase: 'starting' }));
        const started = await startBatch(api, batch.id);
        queryClient.setQueryData(batchKeys.detail(api.baseUrl, started.id), started);
        void queryClient.invalidateQueries({ queryKey: batchKeys.all(api.baseUrl) });
        setState((s) => ({ ...s, phase: 'done' }));
        return started;
      } catch (err) {
        if (batch) await deleteBatch(api, batch.id).catch(() => undefined);
        setState((s) => ({ ...s, phase: 'error', error: (err as Error).message }));
        return null;
      }
    },
    [api, queryClient],
  );

  const cancel = useCallback(() => {
    cancelled.current = true;
  }, []);

  const reset = useCallback(() => setState(initial), []);

  return { state, run, cancel, reset };
}
