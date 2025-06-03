import asyncio
import pytest


@pytest.mark.asyncio(loop_scope="module")
async def test_ro_concurrency(database):
    """Test that multiple RO operations can run concurrently"""
    start_time = asyncio.get_event_loop().time()

    async def ro_operation():
        async with database.init_context(read_only=True):
            await asyncio.sleep(0.1)

    # Run 3 RO operations concurrently
    await asyncio.gather(ro_operation(), ro_operation(), ro_operation())

    end_time = asyncio.get_event_loop().time()
    # Should take ~0.1s if running concurrently
    elapsed = end_time - start_time
    assert elapsed < 0.15


@pytest.mark.asyncio(loop_scope="module")
async def test_rw_blocks_ro(database):
    """Test that RW operations block RO operations"""
    results = []

    async def ro_operation():
        name = asyncio.current_task().get_name()
        async with database.init_context(read_only=True):
            results.append(('start', name))
            await asyncio.sleep(0.1)
            results.append(('end', name))

    async def rw_operation():
        name = asyncio.current_task().get_name()
        async with database.init_context(read_only=False):
            results.append(('start', name))
            await asyncio.sleep(0.1)
            results.append(('end', name))

    # Schedule: RO starts, then RW starts during RO, then another RO
    rw1 = asyncio.create_task(rw_operation(), name='rw-1')
    await asyncio.sleep(0.01)
    ro1 = asyncio.create_task(ro_operation(), name='ro-1')
    await asyncio.gather(rw1, ro1)

    # Verify RW blocked everything
    assert results == [
        ('start', 'rw-1'),
        ('end', 'rw-1'),
        ('start', 'ro-1'),
        ('end', 'ro-1'),
    ]


@pytest.mark.asyncio(loop_scope="module")
async def test_ro_blocks_rw(database):
    """Test that RO operations block RW operations"""
    results = []

    async def ro_operation():
        name = asyncio.current_task().get_name()
        async with database.init_context(read_only=True):
            results.append(('start', name))
            await asyncio.sleep(0.1)
            results.append(('end', name))

    async def rw_operation():
        name = asyncio.current_task().get_name()
        async with database.init_context(read_only=False):
            results.append(('start', name))
            await asyncio.sleep(0.1)
            results.append(('end', name))

    # Schedule: RO starts, then RW starts during RO, then another RO
    ro1 = asyncio.create_task(ro_operation(), name='ro-1')
    await asyncio.sleep(0.01)
    rw1 = asyncio.create_task(rw_operation(), name='rw-1')
    await asyncio.gather(ro1, rw1)

    # Verify RW blocked everything
    assert results == [
        ('start', 'ro-1'),
        ('end', 'ro-1'),
        ('start', 'rw-1'),
        ('end', 'rw-1'),
    ]

@pytest.mark.asyncio(loop_scope="module")
async def test_rw_serialization(database):
    """Test that RW operations don't run concurrently"""
    start_time = asyncio.get_event_loop().time()

    async def rw_operation():
        async with database.init_context(read_only=False):
            await asyncio.sleep(0.1)

    # Run 3 RW operations - should serialize
    await asyncio.gather(rw_operation(), rw_operation(), rw_operation())

    end_time = asyncio.get_event_loop().time()
    # Should take ~0.3s if running serially (3 × 0.1s)
    assert end_time - start_time > 0.25
