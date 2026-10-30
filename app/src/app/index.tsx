import { Link, Stack } from 'expo-router';
import { Pressable } from 'react-native';

import { Card, EmptyState, Screen, ThemedText } from '@/components';
import { useTheme } from '@/theme';

export default function HomeScreen() {
  const { colors } = useTheme();
  return (
    <Screen>
      <Stack.Screen
        options={{
          headerRight: () => (
            <Link href="/settings" asChild>
              <Pressable accessibilityRole="button" hitSlop={12}>
                <ThemedText color={colors.brand}>Settings</ThemedText>
              </Pressable>
            </Link>
          ),
        }}
      />
      <Card>
        <ThemedText variant="title">Marketplace-ready photos</ThemedText>
        <ThemedText muted>
          Snap your products, and CleanShot removes the background, centres them and exports Amazon,
          Flipkart, Meesho and Instagram sizes.
        </ThemedText>
      </Card>
      <EmptyState title="No batches yet" message="Batch processing arrives in a later phase." />
    </Screen>
  );
}
