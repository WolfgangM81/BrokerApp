import NextAuth from "next-auth";

/**
 * Auth.js v5 wired against Authentik via OIDC.
 *
 * Authentik exposes a generic OAuth2 / OIDC provider; we configure it with
 * the standard well-known/openid-configuration URL so issuer + JWKS are
 * discovered automatically.
 *
 * Required env vars (see .env.example):
 *   AUTH_SECRET                     — random 32+ byte secret
 *   AUTH_AUTHENTIK_ID               — OIDC client id
 *   AUTH_AUTHENTIK_SECRET           — OIDC client secret
 *   AUTH_AUTHENTIK_ISSUER           — e.g. https://auth.orbiter/application/o/brokerapp/
 */
export const { handlers, auth, signIn, signOut } = NextAuth({
  trustHost: true,
  session: { strategy: "jwt" },
  providers: [
    {
      id: "authentik",
      name: "Authentik",
      type: "oidc",
      issuer: process.env.AUTH_AUTHENTIK_ISSUER!,
      clientId: process.env.AUTH_AUTHENTIK_ID!,
      clientSecret: process.env.AUTH_AUTHENTIK_SECRET!,
      authorization: { params: { scope: "openid email profile groups" } },
      checks: ["pkce", "state"],
    },
  ],
  callbacks: {
    async jwt({ token, account, profile }) {
      if (account?.access_token) {
        token.accessToken = account.access_token;
        token.accessTokenExpires = account.expires_at ? account.expires_at * 1000 : undefined;
      }
      if (profile?.email) token.email = profile.email;
      if (profile && typeof (profile as { groups?: unknown }).groups !== "undefined") {
        token.groups = (profile as { groups: string[] }).groups;
      }
      return token;
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken as string | undefined;
      session.groups = (token.groups as string[] | undefined) ?? [];
      if (session.user && token.email) session.user.email = token.email as string;
      return session;
    },
  },
  pages: {
    error: "/auth/error",
  },
});
