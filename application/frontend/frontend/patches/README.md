# Assistant UI 0.11.58 compatibility patch

`@assistant-ui__react@0.11.58.patch` preserves `this` when the remote thread
list calls LocalRuntime's `__internal_setGetInitializePromise`. Without it,
combining `useLocalRuntime` with `useRemoteThreadListRuntime` crashes at mount
(`Cannot set properties of undefined`). Both the shipped JavaScript and source
are patched. pnpm applies it on install, including frozen-lockfile installs.

The packaged full preset uses LocalRuntime for stable optimistic message IDs,
edit/reload handlers, and alternative conversation branches while keeping the
existing packaged streaming API. The chat-actions regression suite covers this
composition. Recheck/remove this patch when upgrading Assistant UI.
