# Contribution Guide — DealFlow360

Welcome to the **DealFlow360** repository. This guide establishes the Git branch workflow and development rules for our 4-person team.

## Branches

- **`main`**:
  Stable/demo-ready code. Never develop directly on this branch.
- **`develop`**:
  Integration/testing branch where completed features merge.
- **`feature/person1`**:
  Person 1 development branch.
- **`feature/person2`**:
  Person 2 development branch.
- **`feature/person3`**:
  Person 3 development branch.
- **`feature/person4`**:
  Person 4 development branch.

## Workflow

```text
feature/personX
     ↓
  develop
     ↓
  testing
     ↓
   main
     ↓
production/demo
```

## Rules

- Pull latest `develop` before starting new work.
- Work only on your assigned feature branch.
- Keep commits focused.
- Do not modify another person's module without coordination.
- Do not silently change shared API contracts.
- Do not commit secrets or `.env` files.
- Do not force-push shared branches.
- Do not merge experimental/broken code into `main`.
