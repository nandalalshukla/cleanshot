import { ImageManipulator, SaveFormat } from 'expo-image-manipulator';
import * as ImagePicker from 'expo-image-picker';
import { Platform } from 'react-native';

import type { LocalPhoto } from '@/api/endpoints';

/** Phone cameras shoot 12–50 MP; the worker never needs more than this on the long side. */
const MAX_UPLOAD_SIDE = 3000;
export const MAX_PHOTOS_PER_BATCH = 50;

export interface PickedPhoto extends LocalPhoto {
  width: number;
  height: number;
}

export class PermissionDeniedError extends Error {}

function toPicked(asset: ImagePicker.ImagePickerAsset, index: number): PickedPhoto {
  const ext = asset.mimeType?.split('/')[1]?.replace('jpeg', 'jpg') ?? 'jpg';
  return {
    uri: asset.uri,
    name: asset.fileName ?? `photo-${Date.now()}-${index}.${ext}`,
    mimeType: asset.mimeType ?? 'image/jpeg',
    width: asset.width,
    height: asset.height,
  };
}

export async function pickFromLibrary(limit = MAX_PHOTOS_PER_BATCH): Promise<PickedPhoto[]> {
  const res = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ['images'],
    allowsMultipleSelection: limit > 1,
    selectionLimit: limit,
    orderedSelection: true,
    quality: 1,
  });
  return res.canceled ? [] : res.assets.map(toPicked);
}

export async function takePhoto(): Promise<PickedPhoto | null> {
  const perm = await ImagePicker.requestCameraPermissionsAsync();
  if (!perm.granted) throw new PermissionDeniedError('Camera access is needed to take photos.');
  const res = await ImagePicker.launchCameraAsync({ mediaTypes: ['images'], quality: 0.9 });
  return res.canceled || !res.assets[0] ? null : toPicked(res.assets[0], 0);
}

/**
 * Downscale and re-encode very large photos (and HEIC) to JPEG before upload: saves the seller's
 * mobile data and upload time without affecting output quality.
 */
export async function prepareForUpload(photo: PickedPhoto): Promise<LocalPhoto> {
  if (Platform.OS === 'web') return photo;
  const longest = Math.max(photo.width, photo.height);
  const isJpeg = photo.mimeType === 'image/jpeg';
  if (longest <= MAX_UPLOAD_SIDE && isJpeg) return photo;

  const ctx = ImageManipulator.manipulate(photo.uri);
  if (longest > MAX_UPLOAD_SIDE) {
    ctx.resize(
      photo.width >= photo.height ? { width: MAX_UPLOAD_SIDE } : { height: MAX_UPLOAD_SIDE },
    );
  }
  const ref = await ctx.renderAsync();
  const saved = await ref.saveAsync({ format: SaveFormat.JPEG, compress: 0.92 });
  return {
    uri: saved.uri,
    name: photo.name.replace(/\.\w+$/, '') + '.jpg',
    mimeType: 'image/jpeg',
  };
}
