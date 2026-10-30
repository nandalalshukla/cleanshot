import type { BatchImage, QualityVerdict } from '@/api/types';

export function verdictOf(image: BatchImage): QualityVerdict {
  return image.quality?.verdict ?? 'ok';
}

export function isFlagged(image: BatchImage): boolean {
  return verdictOf(image) !== 'ok';
}

/** The badge a photo tile should show: quality problems outrank a plain "Done". */
export function tileStatus(image: BatchImage) {
  const verdict = verdictOf(image);
  if (image.status === 'done' || image.status === 'failed') {
    if (verdict === 'retake') return 'retake' as const;
    if (verdict === 'warning') return 'flagged' as const;
  }
  return image.status;
}
