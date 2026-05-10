import { useQuery } from "@tanstack/react-query";
import { Link } from "expo-router";
import { useMemo } from "react";
import { ActivityIndicator, FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { makeApiClient } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function Home() {
  const { accessToken, loading, signIn, signOut } = useAuth();
  const api = useMemo(() => makeApiClient(() => accessToken), [accessToken]);

  const watchlists = useQuery({
    queryKey: ["watchlists"],
    queryFn: () => api.listWatchlists(),
    enabled: !!accessToken,
  });

  if (loading) {
    return (
      <SafeAreaView style={styles.center}>
        <ActivityIndicator />
      </SafeAreaView>
    );
  }

  if (!accessToken) {
    return (
      <SafeAreaView style={styles.center}>
        <Text style={styles.title}>BrokerApp</Text>
        <Text style={styles.subtitle}>Mit Authentik anmelden, um Watchlists zu sehen.</Text>
        <Pressable onPress={signIn} style={styles.primary}>
          <Text style={styles.primaryText}>Anmelden</Text>
        </Pressable>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Watchlists</Text>
        <Pressable onPress={signOut} hitSlop={8}>
          <Text style={styles.link}>Abmelden</Text>
        </Pressable>
      </View>
      {watchlists.isLoading ? (
        <ActivityIndicator />
      ) : watchlists.error ? (
        <Text style={styles.error}>{(watchlists.error as Error).message}</Text>
      ) : (watchlists.data ?? []).length === 0 ? (
        <Text style={styles.subtitle}>Noch keine Watchlists.</Text>
      ) : (
        <FlatList
          data={watchlists.data}
          keyExtractor={(item) => item.id}
          contentContainerStyle={{ gap: 8, paddingTop: 12 }}
          renderItem={({ item }) => (
            <Link href={{ pathname: "/watchlists/[id]", params: { id: item.id } }} asChild>
              <Pressable style={styles.card}>
                <Text style={styles.cardTitle}>{item.name}</Text>
                {item.description ? (
                  <Text style={styles.subtitle}>{item.description}</Text>
                ) : null}
              </Pressable>
            </Link>
          )}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, gap: 12 },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: 24, gap: 12 },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  title: { fontSize: 22, fontWeight: "600" },
  subtitle: { fontSize: 14, color: "#666" },
  link: { color: "#2563eb", fontWeight: "500" },
  primary: { backgroundColor: "#111827", paddingHorizontal: 24, paddingVertical: 12, borderRadius: 8 },
  primaryText: { color: "#fff", fontWeight: "600" },
  card: { backgroundColor: "#fff", padding: 16, borderRadius: 8, borderWidth: 1, borderColor: "#e5e5e5" },
  cardTitle: { fontSize: 16, fontWeight: "600" },
  error: { color: "#b91c1c" },
});
