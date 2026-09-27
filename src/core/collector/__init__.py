"""采集：Adapter / AdapterRegistry / Collector / Dispatcher。只依赖 target。"""

from core.collector.adapter import Adapter, FetchedRecord
from core.collector.collector import Collector
from core.collector.dispatcher import Dispatcher
from core.collector.errors import CollectorError, DuplicateAdapterError, UnknownAdapterError
from core.collector.registry import AdapterRegistry, match_query_fields
from core.collector.repository import CursorRepository, ObservationRepository

__all__ = [
    "Adapter",
    "AdapterRegistry",
    "Collector",
    "CollectorError",
    "CursorRepository",
    "Dispatcher",
    "DuplicateAdapterError",
    "ObservationRepository",
    "FetchedRecord",
    "UnknownAdapterError",
    "match_query_fields",
]
