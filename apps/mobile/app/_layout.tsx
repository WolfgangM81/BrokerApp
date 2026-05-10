import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { QueryProvider } from "@/lib/query";

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <QueryProvider>
        <StatusBar style="auto" />
        <Stack screenOptions={{ headerShown: false }} />
      </QueryProvider>
    </SafeAreaProvider>
  );
}
