---
name: fetch-api-data
description: >
  This skill covers patterns for fetching and managing API data.
  Trigger: When working with API interactions in the frontend.
license: Apache-2.0
metadata:
  author: repoforge
  version: "1.0"
  complexity: medium
  token_estimate: 350
  dependencies: []
  related_skills: []
  load_priority: high
---

<!-- L1:START -->
# fetch-api-data

This skill covers patterns for fetching and managing API data.

**Trigger**: When working with API interactions in the frontend.
<!-- L1:END -->

<!-- L2:START -->
## Quick Reference

| Task | Pattern |
|------|---------|
| Fetch API data | `fetchApi` |
| Start a generation process | `startGeneration` |

## Critical Patterns (Summary)
- **Fetch API Data**: Use `fetchApi` to retrieve data from the API.
- **Start Generation Process**: Utilize `startGeneration` to initiate a data generation process.
<!-- L2:END -->

<!-- L3:START -->
## Critical Patterns (Detailed)

### Fetch API Data

Use `fetchApi` to retrieve data from the API, handling errors with `ApiError`.

```typescript
import { fetchApi, ApiError } from './lib/api';

async function getData() {
  try {
    const data = await fetchApi('/endpoint');
    console.log(data);
  } catch (error) {
    if (error instanceof ApiError) {
      console.error('API Error:', error.message);
    }
  }
}
```

### Start Generation Process

Utilize `startGeneration` to initiate a data generation process, allowing for real-time updates.

```typescript
import { startGeneration } from './lib/api';

function initiateGeneration() {
  startGeneration({ type: 'example' })
    .then(response => console.log('Generation started:', response))
    .catch(error => console.error('Error starting generation:', error));
}
```

## When to Use

- When you need to fetch data from an external API.
- When starting a data generation process that requires real-time updates.

## Commands

```bash
docker-compose up
python repoforge/cli.py fetch-data
```

## Anti-Patterns

### Don't: Ignore API Errors

Ignoring API errors can lead to unhandled exceptions and poor user experience.

```typescript
// BAD
async function getData() {
  const data = await fetchApi('/endpoint'); // No error handling
  console.log(data);
}
```
<!-- L3:END -->