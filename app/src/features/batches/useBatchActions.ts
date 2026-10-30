import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Alert } from 'react-native';

import {
  cancelBatch,
  deleteBatch,
  deleteImage,
  replacePhoto,
  retryFailed,
  retryImage,
} from '@/api/endpoints';
import type { Batch } from '@/api/types';
import { prepareForUpload, type PickedPhoto } from '@/features/photos/pickPhotos';
import { useApi } from '@/hooks/useApi';
import { downloadAndShare } from '@/lib/download';

import { batchKeys } from './queries';

/** All mutations available on a batch, with cache updates and user-facing error alerts. */
export function useBatchActions(batchId: string) {
  const api = useApi();
  const qc = useQueryClient();
  const detailKey = batchKeys.detail(api.baseUrl, batchId);

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: detailKey });
    void qc.invalidateQueries({ queryKey: batchKeys.all(api.baseUrl), exact: true });
  };
  const onError = (title: string) => (err: Error) => Alert.alert(title, err.message);
  const setBatch = (b: Batch) => {
    qc.setQueryData(detailKey, b);
    refresh();
  };

  return {
    download: useMutation({
      mutationFn: () =>
        downloadAndShare(
          api,
          `/v1/batches/${batchId}/download`,
          `cleanshot-${batchId}.zip`,
          'application/zip',
        ),
      onError: onError('Download failed'),
    }),
    shareOutput: useMutation({
      mutationFn: (o: { url: string; filename: string }) =>
        downloadAndShare(api, o.url, o.filename, mimeFor(o.filename)),
      onError: onError('Could not share photo'),
    }),
    cancel: useMutation({
      mutationFn: () => cancelBatch(api, batchId),
      onSuccess: setBatch,
      onError: onError('Could not cancel'),
    }),
    retryFailed: useMutation({
      mutationFn: () => retryFailed(api, batchId),
      onSuccess: setBatch,
      onError: onError('Could not retry'),
    }),
    remove: useMutation({
      mutationFn: () => deleteBatch(api, batchId),
      onSuccess: () => {
        qc.removeQueries({ queryKey: detailKey });
        void qc.invalidateQueries({ queryKey: batchKeys.all(api.baseUrl) });
      },
      onError: onError('Could not delete batch'),
    }),
    retryImage: useMutation({
      mutationFn: (imageId: string) => retryImage(api, batchId, imageId),
      onSuccess: refresh,
      onError: onError('Could not retry photo'),
    }),
    replaceImage: useMutation({
      mutationFn: async (v: { imageId: string; photo: PickedPhoto }) =>
        replacePhoto(api, batchId, v.imageId, await prepareForUpload(v.photo)),
      onSuccess: refresh,
      onError: onError('Could not upload the new photo'),
    }),
    deleteImage: useMutation({
      mutationFn: (imageId: string) => deleteImage(api, batchId, imageId),
      onSuccess: refresh,
      onError: onError('Could not remove photo'),
    }),
  };
}

function mimeFor(filename: string): string {
  if (filename.endsWith('.png')) return 'image/png';
  if (filename.endsWith('.webp')) return 'image/webp';
  return 'image/jpeg';
}
