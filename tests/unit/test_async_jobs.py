import asyncio
from sric.jobs import AsyncJobRunner, JobEngine, JobStatus


def test_async_job_runner_completes_and_persists_events(tmp_path):
    async def scenario():
        engine = JobEngine(tmp_path)
        runner = AsyncJobRunner(engine, max_concurrency=1)
        async def worker(ctx):
            ctx.progress(0.5, "half")
            await asyncio.sleep(0)
        job = runner.submit("demo", worker)
        final = await runner.wait(job.job_id)
        assert final.status == JobStatus.COMPLETED
        assert any(e.event_type == "progress" for e in engine.events(job.job_id))
    asyncio.run(scenario())
