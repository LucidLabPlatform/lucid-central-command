# lucid-central-command

Parent repository for the LUCID Central Command stack.

`main` now tracks the active service repos as submodules instead of carrying the older monolithic implementation in-tree.

## Layout

```text
lucid-central-command/
├── lucid-infra
├── lucid-orchestrator
└── lucid-ui
```

## Repos

- `lucid-infra`: broker, database, auth service, compose, and provisioning
- `lucid-orchestrator`: backend API and WebSocket control plane
- `lucid-ui`: operator dashboard

## Legacy Branch

The previous all-in-one repository state has been preserved on the `legacy-monolith` branch.

## Clone

```bash
git clone --recurse-submodules <repo-url>
```

If you already cloned the repo:

```bash
git submodule update --init --recursive
```

## Environment

The canonical env template for the full Central Command stack is:

[` .env.example` ](/Users/farahorfaly/Desktop/LUCID/lucid-central-command/.env.example)

In practice:
- use the shared values there as the source of truth
- copy the values you need into [`lucid-infra/.env`](/Users/farahorfaly/Desktop/LUCID/lucid-central-command/lucid-infra/.env) when running the compose stack
- use the same variables directly when running `lucid-orchestrator`, `lucid-ui`, `lucid-automation`, or `lucid-ai` standalone

## Compose

The main compose entrypoint now lives at the repo root:

[`compose.yaml`](/Users/farahorfaly/Desktop/LUCID/lucid-central-command/compose.yaml)

Typical usage:

```bash
cp .env.example .env
docker compose up -d --build
```

This root compose file builds from:
- `./lucid-infra/lucid-db`
- `./lucid-infra/lucid-auth`
- `./lucid-infra/lucid-emqx`
- `./lucid-orchestrator`
- `./lucid-ui`
