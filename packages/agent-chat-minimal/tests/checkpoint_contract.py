import asyncio
from tempfile import TemporaryDirectory


class CheckpointAdapterContract:
    async def make_adapter(self):
        raise NotImplementedError

    async def close_adapter(self, adapter):
        await adapter.dispose()

    def test_threads_are_isolated_and_deletion_is_session_scoped(self):
        async def scenario():
            adapter = await self.make_adapter()
            try:
                saver = adapter.checkpointer
                await saver.aput(
                    {"configurable": {"thread_id": "session-a", "checkpoint_ns": ""}},
                    {
                        "v": 4,
                        "ts": "2026-01-01T00:00:00+00:00",
                        "id": "checkpoint-a",
                        "channel_values": {"value": "a"},
                        "channel_versions": {"value": 1},
                        "versions_seen": {},
                    },
                    {},
                    {},
                )
                await saver.aput(
                    {"configurable": {"thread_id": "session-b", "checkpoint_ns": ""}},
                    {
                        "v": 4,
                        "ts": "2026-01-01T00:00:00+00:00",
                        "id": "checkpoint-b",
                        "channel_values": {"value": "b"},
                        "channel_versions": {"value": 1},
                        "versions_seen": {},
                    },
                    {},
                    {},
                )

                await adapter.delete_session("session-a")

                assert await saver.aget(
                    {"configurable": {"thread_id": "session-a"}}
                ) is None
                remaining = await saver.aget(
                    {"configurable": {"thread_id": "session-b"}}
                )
                assert remaining is not None
                assert remaining["channel_values"] == {"value": "b"}
            finally:
                await self.close_adapter(adapter)

        asyncio.run(scenario())


class TemporaryCheckpointAdapterContract(CheckpointAdapterContract):
    adapter_type = None

    async def make_adapter(self):
        temporary = TemporaryDirectory()
        adapter = await self.adapter_type.open(f"{temporary.name}/checkpoints.db")
        adapter._contract_temporary = temporary
        return adapter

    async def close_adapter(self, adapter):
        await adapter.dispose()
        adapter._contract_temporary.cleanup()
