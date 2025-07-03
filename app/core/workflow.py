import asyncio
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime
from collections import OrderedDict
import contextvars
from app.models.workflow_models import (
    WorkflowContext, WorkflowError, WorkflowProgress, WorkflowLimits, WorkflowHooks
)
from app.utils.otel_utils import start_trace
from app.utils.error_utils import log_and_raise, log_warning

# Context variable for per-run context isolation
current_workflow_context: contextvars.ContextVar[Optional[WorkflowContext]] = contextvars.ContextVar("current_workflow_context", default=None)

class IngestionWorkflow:
    def __init__(self, ingestion_engine, gcp_service, metrics_service, limits: Optional[WorkflowLimits] = None, hooks: Optional[WorkflowHooks] = None):
        self.ingestion_engine = ingestion_engine
        self.gcp_service = gcp_service
        self.metrics_service = metrics_service
        self.limits = limits or WorkflowLimits()
        self.hooks = hooks or WorkflowHooks()
        self.active_runs: OrderedDict[str, WorkflowContext] = OrderedDict()
        self.completed_runs: List[WorkflowContext] = []  # For stub; replace with persistent storage
        self.lock = asyncio.Lock()

    def create_context(self, source: str, **metadata) -> WorkflowContext:
        run_id = str(uuid.uuid4())
        trace_id = str(uuid.uuid4())  # Replace with real trace if available
        correlation_id = str(uuid.uuid4())
        progress = WorkflowProgress(stage="starting", progress_percentage=0.0)
        context = WorkflowContext(
            run_id=run_id,
            source=source,
            start_time=datetime.utcnow(),
            status="pending",
            progress=progress,
            trace_id=trace_id,
            correlation_id=correlation_id,
            baggage=metadata.get("baggage", {}),
            hooks=self.hooks,
            metadata=metadata
        )
        return context

    async def ingest_from_file(self, file_path: str, **kwargs) -> WorkflowContext:
        context = self.create_context(source="file_upload", **kwargs)
        token = current_workflow_context.set(context)
        try:
            await self._run_with_limits(self._ingest_file_run, context, file_path, **kwargs)
        finally:
            current_workflow_context.reset(token)
        return context

    async def ingest_from_gcp(self, query_params: Dict, **kwargs) -> WorkflowContext:
        context = self.create_context(source="gcp_api", **kwargs)
        token = current_workflow_context.set(context)
        try:
            await self._run_with_limits(self._ingest_gcp_run, context, query_params, **kwargs)
        finally:
            current_workflow_context.reset(token)
        return context

    async def ingest_from_stream(self, stream_config: Dict, **kwargs) -> WorkflowContext:
        context = self.create_context(source="stream", **kwargs)
        token = current_workflow_context.set(context)
        try:
            await self._run_with_limits(self._ingest_stream_run, context, stream_config, **kwargs)
        finally:
            current_workflow_context.reset(token)
        return context

    async def _run_with_limits(self, coro, context: WorkflowContext, *args, **kwargs):
        async with self.lock:
            if len(self.active_runs) >= self.limits.max_concurrent_runs:
                log_and_raise("Max concurrent workflow runs reached", context=context.dict())
            self.active_runs[context.run_id] = context
        try:
            context.status = "running"
            if context.hooks and context.hooks.on_start:
                await self._maybe_call_hook(context.hooks.on_start, context)
            await coro(context, *args, **kwargs)
            context.status = "completed"
            context.progress.stage = "complete"
            context.progress.progress_percentage = 100.0
            if context.hooks and context.hooks.on_complete:
                await self._maybe_call_hook(context.hooks.on_complete, context)
        except Exception as e:
            context.status = "failed"
            context.error = WorkflowError(
                error_type=type(e).__name__,
                stage=context.progress.stage,
                recoverable=False,
                retry_count=0,
                context={"exception": str(e)}
            )
            if context.hooks and context.hooks.on_error:
                await self._maybe_call_hook(context.hooks.on_error, context, e)
            log_warning("Workflow run failed", {"run_id": context.run_id, "error": str(e)})
        finally:
            context.end_time = datetime.utcnow()
            async with self.lock:
                self.active_runs.pop(context.run_id, None)
                self.completed_runs.append(context)
                if len(self.completed_runs) > 1000:
                    self.completed_runs.pop(0)

    async def _maybe_call_hook(self, hook, *args, **kwargs):
        if asyncio.iscoroutinefunction(hook):
            await hook(*args, **kwargs)
        else:
            hook(*args, **kwargs)

    async def _ingest_file_run(self, context: WorkflowContext, file_path: str, **kwargs):
        context.progress.stage = "ingesting"
        context.progress.progress_percentage = 10.0
        with start_trace("workflow_file_ingest"):
            result = self.ingestion_engine.ingest_from_file(file_path, **kwargs)
            context.progress.logs_processed = result.processed_count
            context.progress.progress_percentage = 80.0
            context.metadata["ingestion_result"] = result.dict()
        context.progress.stage = "buffering"
        context.progress.progress_percentage = 90.0
        # Buffer status, etc. can be updated here
        context.progress.stage = "complete"
        context.progress.progress_percentage = 100.0

    async def _ingest_gcp_run(self, context: WorkflowContext, query_params: Dict, **kwargs):
        context.progress.stage = "ingesting"
        context.progress.progress_percentage = 10.0
        with start_trace("workflow_gcp_ingest"):
            result = self.ingestion_engine.ingest_from_gcp(query_params, **kwargs)
            context.progress.logs_processed = result.processed_count
            context.progress.progress_percentage = 80.0
            context.metadata["ingestion_result"] = result.dict()
        context.progress.stage = "buffering"
        context.progress.progress_percentage = 90.0
        context.progress.stage = "complete"
        context.progress.progress_percentage = 100.0

    async def _ingest_stream_run(self, context: WorkflowContext, stream_config: Dict, **kwargs):
        context.progress.stage = "ingesting"
        context.progress.progress_percentage = 10.0
        with start_trace("workflow_stream_ingest"):
            result = self.ingestion_engine.ingest_stream(stream_config, **kwargs)
            context.progress.logs_processed = result.processed_count
            context.progress.progress_percentage = 80.0
            context.metadata["ingestion_result"] = result.dict()
        context.progress.stage = "buffering"
        context.progress.progress_percentage = 90.0
        context.progress.stage = "complete"
        context.progress.progress_percentage = 100.0

    async def get_run_status(self, run_id: str) -> Optional[WorkflowContext]:
        async with self.lock:
            return self.active_runs.get(run_id) or next((c for c in self.completed_runs if c.run_id == run_id), None)

    async def get_active_runs(self) -> List[WorkflowContext]:
        async with self.lock:
            return list(self.active_runs.values())

    async def cancel_run(self, run_id: str) -> bool:
        # For now, just mark as cancelled; true cancellation would require cancellation tokens
        async with self.lock:
            context = self.active_runs.get(run_id)
            if context:
                context.status = "cancelled"
                return True
            return False

    async def retry_failed_run(self, run_id: str) -> Optional[WorkflowContext]:
        async with self.lock:
            context = next((c for c in self.completed_runs if c.run_id == run_id and c.status == "failed"), None)
        if context:
            # Re-run with same parameters (stub)
            # You may want to deep copy context/metadata and reset progress
            return await self.ingest_from_file(context.metadata.get("file_path"))  # Example for file runs
        return None

    async def get_pipeline_metrics(self) -> Dict[str, Any]:
        # Aggregate metrics from all runs and the metrics service
        return self.metrics_service.get_snapshot().dict()

    async def get_buffer_status(self) -> Dict[str, Any]:
        return self.ingestion_engine.get_buffer().dict()

    async def health_check(self) -> Dict[str, Any]:
        return {"status": "ok", "active_runs": len(self.active_runs)}

    async def update_context(self, run_id: str, updates: Dict) -> None:
        async with self.lock:
            context = self.active_runs.get(run_id) or next((c for c in self.completed_runs if c.run_id == run_id), None)
            if context:
                for k, v in updates.items():
                    setattr(context, k, v) 