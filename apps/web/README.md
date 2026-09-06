# Attesia web

Minimal Next.js App Router foundation. Use Node.js 22.22.3 (`.nvmrc`) and
npm 10.9.8. npm is bundled with Node.js; this app owns the monorepo's only
JavaScript lockfile. Python dependencies remain managed by uv in `apps/api`.

## Local development

```sh
cd apps/web
nvm use # if you use nvm
npm ci
cp .env.example .env.local
npm run lint
npm run typecheck
npm run check:api
npm run build
npm run dev
```

Open http://localhost:3000. To serve a production build, run `npm run start`
after `npm run build`. The placeholder works without a running API or env file.
`typecheck` runs `next typegen` first, so it also works on a fresh checkout.

The scripts use Next.js's default Turbopack. In restricted environments where
Turbopack's CSS worker cannot bind a local port, use the built-in alternative:
`npm run build -- --webpack` and `npm run dev -- --webpack`. Both were checked
locally; the default Turbopack build still needs verification outside that
restriction (including the first frontend CI run).

There is no root package or workspace tooling yet. From the repository root,
use `npm --prefix apps/web ci` and `npm --prefix apps/web run <script>`.

## Structure and state

```text
src/
  app/                 # routes, layouts, providers, global styles
  widgets/             # composed interface sections
  features/            # user actions / use cases
  entities/            # domain models and their presentation
  shared/
    api/               # fetch transport and configured client
```

The three unused layers contain only `.gitkeep`. Create domain slices and
`shared/ui`, `shared/lib`, or `shared/config` when actual code needs them.
Dependencies flow down: app -> widgets -> features -> entities -> shared.
Shared code must not import upper layers. Avoid global components/hooks/utils
folders, blanket barrel exports, and wrappers around TanStack Query hooks.

| State | Owner |
| --- | --- |
| Server state | TanStack Query |
| Local UI state | React `useState` / `useReducer` |
| Form state | React Hook Form |
| Validation | Zod |
| Global client state | Zustand only if a real need appears; not installed |

Never duplicate server state in a client store. React Hook Form and Zod are
installed as requested; there are no forms or speculative schemas yet.

`app/layout.tsx` and `app/page.tsx` remain Server Components. Only
`app/providers.tsx` declares `use client`. It passes server-rendered children
through `QueryClientProvider`, creates a fresh QueryClient on the server, and
retains one client in the browser even if rendering suspends. Query defaults
are unchanged. Add prefetching/hydration and query-specific caching policies
with the first real data flow.

## API client

Set `NEXT_PUBLIC_API_URL` in `.env.local`, for example:

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1/
```

This is a public, browser-visible value, never a secret. Next.js embeds public
env values at build time: set the correct URL before building for each target.
The URL must be absolute HTTP(S), include `/api/v1/`, and have no query or hash.

Import `api` from `@/shared/api/api`. `api<T>("relative/path/", options)`:

- Resolves endpoints under the configured base, preserving trailing slashes.
- Serializes `body` as JSON and sets JSON request/accept headers.
- Accepts native fetch options, including `signal`, headers, and credentials.
- Uses fetch's default credentials policy; pass `credentials: "include"`
  explicitly when a cross-origin cookie request needs it.
- Returns parsed JSON as `T`, or `undefined` for an empty response
  (use `api<void>` for endpoints such as DELETE returning 204).
- Throws `ApiError` with `status` and `data` for non-2xx responses. Error data
  is parsed JSON, raw text for non-JSON errors, or undefined for an empty body.
- Preserves network/abort errors and rejects malformed JSON in a successful
  non-empty response. It performs no retries or auth handling.

The generic is a TypeScript assertion, not runtime validation. Validate external
data with Zod in the owning entity/feature when its schema exists. This transport
is JSON-only; it does not implement file uploads or streaming.

`shared/api/client.ts` is framework-independent; `shared/api/api.ts` alone wires
the Next.js environment variable. Configuration is checked on request, so an
unused API client cannot block building the placeholder. `scripts/check-api.ts`
uses native Node assertions and a mocked fetch to check real transport behavior
without a test framework or backend dependency.

The current Django backend does not configure CORS. Before browser integration,
allow the frontend origin on the backend; cookie-based requests also need the
appropriate credentials, cookie and CSRF policy. Server-side fetch does not
automatically forward a visitor's cookies. That integration belongs to the
actual auth/data work, not this foundation.

## Checks and CI

`frontend-ci.yml` runs on pull requests to main touching this app or its workflow:
`npm ci`, lint, typecheck, API check, production build. Node and action revisions
are pinned. The backend workflow is unchanged. No backend calls are made during
the build. Generated `.next`, `next-env.d.ts`, TypeScript build info and local env
files are ignored; `.env.example` is tracked.
`next.config.ts` disables automatic agent instruction file generation so
`next dev` does not add unsolicited `AGENTS.md` / `CLAUDE.md` files.

ESLint 9 is deprecated upstream but is still required by the React/a11y plugins
in the current Next.js ESLint preset (their peer ranges exclude ESLint 10).
TypeScript 5.9 stays within the preset's supported TypeScript range. Upgrade
these together when the preset's dependencies support the newer major versions.

Setup references: [Next.js installation](https://nextjs.org/docs/app/getting-started/installation),
[TanStack Query App Router setup](https://tanstack.com/query/latest/docs/framework/react/guides/advanced-ssr),
[Tailwind CSS with Next.js](https://tailwindcss.com/docs/installation/framework-guides/nextjs).
