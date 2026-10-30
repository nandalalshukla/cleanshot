import { Image, type ImageProps } from 'expo-image';
import { StyleSheet } from 'react-native';

import { useApi } from '@/hooks/useApi';
import { useTheme } from '@/theme';

/** expo-image bound to the worker: resolves relative paths and sends auth headers. */
export function RemoteImage({
  path,
  style,
  ...rest
}: Omit<ImageProps, 'source'> & { path: string }) {
  const api = useApi();
  const { colors } = useTheme();
  return (
    <Image
      source={api.imageSource(path)}
      // expo-image on web can't take nested style arrays, so always pass a flat object.
      style={StyleSheet.flatten([{ backgroundColor: colors.surfaceMuted }, style])}
      contentFit="contain"
      transition={150}
      {...rest}
    />
  );
}
