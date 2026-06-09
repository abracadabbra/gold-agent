<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

## Testing

```bash
npm test              # run all tests (Jest 30)
npm run test:watch    # watch mode
```

- Test files live in `src/__tests__/` with names `*.test.ts` or `*.test.tsx`
- Jest config: `jest.config.js` (uses `next/jest` transformer)
- Setup: `jest.setup.ts` (imports `@testing-library/jest-dom`)
- 39 tests covering shared UI components + signal-gauge + top-metrics + system-status

### Conventions
- Mock `@/lib/api` for component tests that call API hooks
- Use `jest.mock('@/lib/api', ...)` and provide mock `resolvedValue` / `rejectedValue`
- New test files must be added under `src/__tests__/`
