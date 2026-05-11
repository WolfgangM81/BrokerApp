import { useQuery } from "@tanstack/react-query";
import { Stack, useLocalSearchParams } from "expo-router";
import { useMemo } from "react";
import { ActivityIndicator, FlatList, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { makeApiClient } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function WatchlistDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { accessToken } = useAuth();
  const api = useMemo(() => makeApiClient(() => accessToken), [accessToken]);
  const watchlist = useQuery({
    queryKey: ["watchlist", id],
    queryFn: () => api.getWatchlist(id!),
    enabled: !!id && !!accessToken,
  });

  return (
    <SafeAreaView style={styles.container}>
      <Stack.Screen options={{ title: watchlist.data?.name ?? "Watchlist", headerShown: true }} />
      {watchlist.isLoading ? (
        <ActivityIndicator />
      ) : watchlist.error ? (
        <Text style={styles.error}>{(watchlist.error as Error).message}</Text>
      ) : !watchlist.data ? null : (
        <FlatList
          data={watchlist.data.members}
          keyExtractor={(m) => m.asset_id}
          contentContainerStyle={{ gap: 8 }}
          ListEmptyComponent={<Text style={styles.subtitle}>Keine Mitglieder.</Text>}
          renderItem={({ item }) => (
            <View style={styles.row}>
              <Text style={styles.id}>{item.asset_id.slice(0, 8)}…</Text>
              <Text style={styles.subtitle}>{new Date(item.added_at).toLocaleDateString()}</Text>
            </View>
          )}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    padding: 12,
    borderBottomWidth: 1,
    borderBottomColor: "#e5e5e5",
  },
  id: { fontFamily: "Menlo", fontSize: 14 },
  subtitle: { color: "#666", fontSize: 12 },
  error: { color: "#b91c1c" },
});
