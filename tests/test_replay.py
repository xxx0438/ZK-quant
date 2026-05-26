import orjson
import pytest

from echo_data.replay import Replayer, SnapshotIntegrityError, SnapshotNotFound
from echo_data.schema import Inputs, StoredSnapshot
from echo_data.snapshot import compute_snapshot_hash

class FakeStore:
    def __init__(self):
        self._snaps: dict[str, StoredSnapshot] = {}
    async def get_snapshot(self, h):
        return self._snaps.get(h)

class FakeCache:
    def __init__(self):
        self._data: dict[str, bytes] = {}
    async def get_snapshot(self, h):
        return self._data.get(h)
    async def cache_snapshot(self, h, body, ttl_s=0):
        self._data[h] = body

@pytest.mark.asyncio
async def test_replay_round_trip():
    inputs = Inputs(asset="ETH", timestamp=1000)
    h = compute_snapshot_hash(inputs)
    inputs_with_hash = inputs.model_copy(update={"snapshot_hash": h})
    body = orjson.dumps(inputs_with_hash.model_dump())

    cache = FakeCache()
    await cache.cache_snapshot(h, body)
    replayer = Replayer(store=FakeStore(), cache=cache)

    restored = await replayer.replay(h)
    assert restored.snapshot_hash == h
    assert restored.asset == "ETH"

@pytest.mark.asyncio
async def test_replay_missing_raises():
    replayer = Replayer(store=FakeStore(), cache=FakeCache())
    with pytest.raises(SnapshotNotFound):
        await replayer.replay("doesnotexist")

@pytest.mark.asyncio
async def test_replay_integrity_failure():
    # Forge a snapshot whose body doesn't match the claimed hash
    bad_body = orjson.dumps({"asset": "ETH", "timestamp": 1000, "snapshot_hash": "fake"})
    cache = FakeCache()
    await cache.cache_snapshot("claimed_hash_that_wont_match", bad_body)
    replayer = Replayer(store=FakeStore(), cache=cache)
    with pytest.raises(SnapshotIntegrityError):
        await replayer.replay("claimed_hash_that_wont_match")
