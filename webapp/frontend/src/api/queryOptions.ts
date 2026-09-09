// Read screens must reload after returning from an edit and must not silently
// replace an open form or admin action with a background refresh.
export const freshQueryOptions = {
  staleTime: 0,
  gcTime: 0,
  retry: false,
  // Even an offline browser must reach the bounded fetch/error path instead of
  // pausing indefinitely or rendering an unfetched list as empty.
  networkMode: 'always',
  refetchOnWindowFocus: false,
  refetchOnReconnect: false,
} as const;
