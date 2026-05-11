# Step 70 — Authentik: OIDC apps and groups

You need **two OIDC applications** (web and mobile) and **one group**
(admin). Authentik calls these _Provider + Application + Group_.

## 70.1 Create the group

Authentik UI → **Directory** → **Groups** → **Create**

| Field   | Value              |
| ------- | ------------------ |
| Name    | `brokerapp-admins` |
| Members | add yourself       |

Members of this group will pass the `require_admin` check in
`apps/api/src/api/auth.py`. Everyone else can read/write only their own
watchlists and trades.

## 70.2 Provider — web app

Authentik UI → **Applications** → **Providers** → **Create**

Choose **OAuth2/OpenID Provider**.

| Field                      | Value                                                                                                                                 |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Name                       | `brokerapp-web-provider`                                                                                                              |
| Authentication flow        | `default-authentication-flow`                                                                                                         |
| Authorization flow         | `default-provider-authorization-explicit-consent`                                                                                     |
| **Client type**            | **Confidential**                                                                                                                      |
| Client ID                  | `brokerapp` (this is what `AUTH_AUTHENTIK_ID` becomes)                                                                                |
| Client Secret              | _Generate_, then **copy** — you'll Vault this in step 80                                                                              |
| Redirect URIs / Origins    | `https://brokerapp.orbiter/api/auth/callback/authentik`                                                                               |
| Signing Key                | `authentik Self-signed Certificate`                                                                                                   |
| Subject mode               | Based on the User's email                                                                                                             |
| Include claims in id_token | ✅                                                                                                                                    |
| Scopes                     | `openid`, `email`, `profile`, `goauthentik.io/providers/oauth2/scope-openid` (default), and **add the `groups` scope** if not present |

### Add the `groups` scope mapping (one-time, cluster-wide)

If `groups` is not in the Scope Mappings list:

Authentik UI → **Customisation** → **Scope mappings** → **Create**

| Field      | Value                                                       |
| ---------- | ----------------------------------------------------------- |
| Name       | `groups`                                                    |
| Scope name | `groups`                                                    |
| Expression | `return {"groups": [g.name for g in user.ak_groups.all()]}` |

Save, then come back to the provider and attach this scope.

## 70.3 Application — web app

Authentik UI → **Applications** → **Applications** → **Create**

| Field              | Value                                              |
| ------------------ | -------------------------------------------------- |
| Name               | `BrokerApp`                                        |
| Slug               | `brokerapp`                                        |
| Provider           | `brokerapp-web-provider`                           |
| Launch URL         | `https://brokerapp.orbiter`                        |
| Open in new tab    | optional                                           |
| Policy engine mode | `any`                                              |
| Policy bindings    | (none — everyone in your homelab can authenticate) |

## 70.4 Provider — mobile app

Authentik UI → **Applications** → **Providers** → **Create**

| Field                   | Value                                       |
| ----------------------- | ------------------------------------------- |
| Name                    | `brokerapp-mobile-provider`                 |
| **Client type**         | **Public** (PKCE-only, no secret)           |
| Client ID               | `brokerapp-mobile`                          |
| Redirect URIs / Origins | `brokerapp://auth/callback`                 |
| Scopes                  | same as web (`openid email profile groups`) |

## 70.5 Application — mobile app

Authentik UI → **Applications** → **Applications** → **Create**

| Field    | Value                       |
| -------- | --------------------------- |
| Name     | `BrokerApp Mobile`          |
| Slug     | `brokerapp-mobile`          |
| Provider | `brokerapp-mobile-provider` |

## 70.6 Get the URLs you'll need

```bash
ISSUER=https://auth.orbiter/application/o/brokerapp/
JWKS=${ISSUER}jwks/
echo "AUTHENTIK_ISSUER=$ISSUER"
echo "AUTHENTIK_JWKS_URL=$JWKS"
curl -sS "$JWKS" | jq '.keys[0].kid'   # should print a kid string
```

If the JWKS endpoint returns a key, the provider is up.

## 70.7 (Optional) Verify the OIDC discovery document

```bash
curl -s https://auth.orbiter/application/o/brokerapp/.well-known/openid-configuration | jq .
```

You should see `authorization_endpoint`, `token_endpoint`,
`userinfo_endpoint`, and `jwks_uri`. The values in
`apps/api/src/api/config.py` (`authentik_issuer`,
`authentik_audience`, `authentik_jwks_url`) align with these.

Next: [80-vault.md](./80-vault.md).
