import { redirect } from "next/navigation";
import { auth } from "@/auth";

/**
 * Server-side auth guard for App-Router pages.
 *
 * The edge middleware only verifies cookie *presence*; that's defense in
 * depth, not authorization. Every page that handles user data must call
 * this on the server to make sure the session is valid + extract the
 * trusted identity.
 *
 * Throws a redirect to /auth/signin if not authenticated.
 */
export async function requireSession() {
  const session = await auth();
  if (!session?.user) {
    redirect("/auth/signin");
  }
  return session;
}
