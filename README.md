# Attesia

**An in-progress platform for events, achievements, and digital credentials.**

Attesia explores how organizations can register event participants, record achievements, and issue structured credentials. This is a **collaborative project in development**, not a launched blockchain product or a production credential network.

**Tech stack:** Python 3.12+, Django 6.1, Django REST Framework, PostgreSQL, pytest, Docker Compose; Next.js 16, React 19, and TypeScript for the frontend foundation.

## Project overview

The backend models a workflow from an organization hosting an event to a participant receiving a credential for an achievement.

- **Organizations** with owner, admin, and member roles.
- **Events**, participants, and event status changes.
- **Achievements** such as placements, finalist status, nominations, and participation.
- **Finalization and credential issuance**, connecting event outcomes to a recipient.
- **Credential records** with issuer, recipient, event and achievement snapshots, and revocation metadata.

## Engineering highlights

### Domain-oriented Django backend

```text
apps/api/
├── app/
│   ├── core/                  # Shared API and authentication
│   └── modules/
│       ├── users/
│       ├── organizations/
│       ├── events/
│       └── credentials/
├── config/
├── tests/
└── manage.py

apps/web/                     # Next.js frontend foundation
```

REST endpoints are versioned under `/api/v1/`. Database constraints cover organization membership uniqueness, valid organization roles, and event date consistency.

### Authentication and authorization

The backend uses a custom, email-based Django user model and access/refresh token handling, including persisted refresh-token revocation. Organization roles and ownership are represented in the data model and enforced in the application.

### Credential snapshots

Issued credential records retain key organization, event, recipient, and achievement details so the credential's contents are not entirely dependent on mutable live relationships. The data model includes revocation time, reason, and actor.

### Tests

The repository includes pytest coverage for authentication, organizations, events, achievements, participant behavior, credentials, and issuance/finalization flows.

## Run locally

**Requirements:** Git, Docker with Docker Compose; Python 3.12+ and `uv` for working on the backend directly.

```bash
git clone https://github.com/an1skat/attesia.git
cd attesia
cp apps/api/.env.example apps/api/.env
```

Fill in the required Django and PostgreSQL values in `apps/api/.env`, then start the stack:

```bash
docker compose up --build
```

The backend is exposed on **http://localhost:8000**, with a health route at `/api/v1/health/`. Frontend instructions are in [apps/web/README.md](apps/web/README.md).

## My contribution and status

Attesia is a team project. My work focuses on the **credential-related backend domain**, alongside API design and backend engineering discussions. Event functionality has also been developed by teammates; this repository is **not** presented as a solo project.

The frontend is currently a technical foundation. Models, API features, and tests should not be confused with a finished end-user verification platform.
