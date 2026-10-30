import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';

import { ApiClient } from '@/api/client';
import { getHealth } from '@/api/endpoints';
import { Button, Card, Screen, TextField, ThemedText } from '@/components';
import { normalizeUrl, useSettings } from '@/lib/settings';
import { useTheme } from '@/theme';

export default function SettingsScreen() {
  const { settings, update } = useSettings();
  const { colors } = useTheme();
  const [apiUrl, setApiUrl] = useState(settings.apiUrl);
  const [apiKey, setApiKey] = useState(settings.apiKey);

  const test = useMutation({
    mutationFn: () => getHealth(new ApiClient({ apiUrl: normalizeUrl(apiUrl), apiKey })),
  });

  const dirty = normalizeUrl(apiUrl) !== settings.apiUrl || apiKey !== settings.apiKey;

  return (
    <Screen>
      <Card>
        <ThemedText variant="heading">Processing server</ThemedText>
        <TextField
          label="Server URL"
          value={apiUrl}
          onChangeText={setApiUrl}
          keyboardType="url"
          placeholder="http://192.168.1.20:8000"
          hint="Your phone and the CleanShot worker must be on the same network (or use a public URL)."
        />
        <TextField
          label="API key (optional)"
          value={apiKey}
          onChangeText={setApiKey}
          secureTextEntry
          placeholder="Leave empty if the server has no key"
        />
        <Button
          title="Test connection"
          variant="secondary"
          loading={test.isPending}
          onPress={() => test.mutate()}
        />
        {test.isSuccess ? (
          <ThemedText color={colors.success}>Connected · worker v{test.data.version}</ThemedText>
        ) : null}
        {test.isError ? <ThemedText color={colors.danger}>{test.error.message}</ThemedText> : null}
        <Button title="Save" disabled={!dirty} onPress={() => update({ apiUrl, apiKey })} />
      </Card>
    </Screen>
  );
}
