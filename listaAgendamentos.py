from rq import Queue
from redis import Redis
from rq.job import Job
from rq_scheduler import Scheduler
import redis

redis_conn = Redis.from_url("redis://localhost:6379", decode_responses=False)
scheduler = Scheduler(connection=redis_conn)
CHANNEL = "canal_eventos"
jobs_with_times = scheduler.get_jobs(with_times=True)

for job, scheduled_time in jobs_with_times:
    print(f"Job ID: {job.get_id()}")
    print(f"Scheduled Time: {scheduled_time}")
    print(f"Func: {job.func_name}")
    print("-----")


q = Queue('canal_eventos', connection=redis_conn)

finished_registry = q.finished_job_registry
finished_job_ids = finished_registry.get_job_ids()

print("Jobs que já foram processados com sucesso:")
for job_id in finished_job_ids:
    job = Job.fetch(job_id, connection=redis_conn)
    print(f"Job ID: {job.id}")
    print(f"Descrição: {job.description}")
    print(f"Resultado: {job.result}")
    print(f"Enfileirado em: {job.enqueued_at}")
    print(f"Concluído em: {job.ended_at}")
    print("-----")

failed_registry = q.failed_job_registry
failed_job_ids = failed_registry.get_job_ids()

print("Jobs com falhas:")
for job_id in failed_job_ids:
    job = Job.fetch(job_id, connection=redis_conn)
    print(f"Job ID: {job.id} falhou com exceção {job.exc_info}")
