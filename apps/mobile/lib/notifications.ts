import * as Notifications from "expo-notifications";
import { Platform } from "react-native";

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

/** Ask for notification permission and return the Expo push token (if any). */
export async function registerForPushNotifications(): Promise<string | null> {
  if (Platform.OS === "android") {
    await Notifications.setNotificationChannelAsync("alerts", {
      name: "Alerts",
      importance: Notifications.AndroidImportance.HIGH,
      sound: "default",
    });
  }
  const settings = await Notifications.getPermissionsAsync();
  let status = settings.status;
  if (status !== "granted") {
    const req = await Notifications.requestPermissionsAsync();
    status = req.status;
  }
  if (status !== "granted") return null;
  const token = await Notifications.getExpoPushTokenAsync();
  return token.data ?? null;
}
