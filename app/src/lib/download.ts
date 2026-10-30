import { Directory, File, Paths } from 'expo-file-system';
import * as Sharing from 'expo-sharing';
import { Platform } from 'react-native';

import type { ApiClient } from '@/api/client';

/**
 * Download a worker file (e.g. the batch ZIP) to the cache and open the share sheet so the
 * seller can save it to Files / Drive or send it on WhatsApp.
 */
export async function downloadAndShare(
  api: ApiClient,
  path: string,
  filename: string,
  mimeType: string,
): Promise<void> {
  const url = api.url(path);
  if (Platform.OS === 'web') {
    const res = await fetch(url, { headers: api.authHeaders });
    if (!res.ok) throw new Error(`Download failed (${res.status})`);
    const href = URL.createObjectURL(await res.blob());
    const a = document.createElement('a');
    a.href = href;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(href);
    return;
  }

  const dir = new Directory(Paths.cache, 'downloads');
  if (!dir.exists) dir.create({ intermediates: true });
  const file = await File.downloadFileAsync(url, new File(dir, filename), {
    headers: api.authHeaders,
    idempotent: true,
  });
  if (!(await Sharing.isAvailableAsync())) {
    throw new Error('Sharing is not available on this device.');
  }
  await Sharing.shareAsync(file.uri, { mimeType, dialogTitle: filename });
}
