import { QueryClientProvider } from '@tanstack/react-query';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { queryClient } from '@/lib/queryClient';
import { SettingsProvider } from '@/lib/settings';
import { useTheme } from '@/theme';

export default function RootLayout() {
  const { colors, dark } = useTheme();
  return (
    <SafeAreaProvider>
      <SettingsProvider>
        <QueryClientProvider client={queryClient}>
          <StatusBar style={dark ? 'light' : 'dark'} />
          <Stack
            screenOptions={{
              headerStyle: { backgroundColor: colors.surface },
              headerTintColor: colors.text,
              contentStyle: { backgroundColor: colors.background },
            }}
          >
            <Stack.Screen name="index" options={{ title: 'CleanShot' }} />
            <Stack.Screen name="settings" options={{ title: 'Settings', presentation: 'modal' }} />
            <Stack.Screen name="batch/new" options={{ title: 'New batch' }} />
            <Stack.Screen name="batch/[id]/index" options={{ title: 'Batch' }} />
            <Stack.Screen name="batch/[id]/[imageId]" options={{ title: 'Photo' }} />
          </Stack>
        </QueryClientProvider>
      </SettingsProvider>
    </SafeAreaProvider>
  );
}
