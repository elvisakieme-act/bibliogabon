# BiblioGABON Frontend

Reader-facing web frontend for BiblioGABON.

## Commands

- `npm install`: install frontend dependencies.
- `npm run dev`: start the Vite development server.
- `npm run build`: type-check and build production assets.
- `npm run lint`: run ESLint.
- `npm run test`: run Vitest tests.

## Configuration

Copy `.env.example` to `.env.local` and set:

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```

The frontend consumes the Django API under `/api/v1/`.
