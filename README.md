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
