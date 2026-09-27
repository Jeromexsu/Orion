from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, SerializeAsAny

from core.target import Observation, ObservedPoint, QueryKey, QuerySpec

Query = dict[type[QueryKey], Any]
"""这次查询：查询键 → 取值，如 {Icao24: "780a3b"}。由 collector 按上游挑出的查询方式组装。"""


class FetchedRecord(BaseModel):
    """Adapter 从上游拿到的一条记录：观测实例 + 来源信息。

    observation 由 Adapter 直接构造成观察点的观测类（如 PositionObservation），字段写错在 Adapter 里当场报错；
    collector 只检查它的类型是否与上游服务的观察点一致。
    """

    model_config = ConfigDict(frozen=True)

    observation: SerializeAsAny[Observation]
    occurred_at: datetime
    source_id: str              # 全局唯一，去重用，如 "adsb#881"
    raw: dict[str, Any] | None = None   # 上游原始响应，便于排查


class Adapter(ABC):
    """上游基类。一个上游（数据提供方，如 OpenSky）一个子类，放在 plugins/collector/ 下：

        class OpenSkyAdapter(Adapter):
            name = "opensky"
            observed_points = frozenset({Position})
            query_key_sets = (frozenset({Icao24}),)

            def fetch(self, spec, query, since): ...

    类属性的类型在这里声明，子类直接赋值即可。
    一个上游可以服务多个观察点：fetch 按 spec.observed_point 分支，返回对应观察点的观测；
    游标、订阅、路由都按（可观测目标, 上游）组织，可观测目标里已带观察点，所以互不干扰。
    Adapter 不关心目标类型，只关心观察点（输出契约）和查询键（输入契约）——不同目标类型只要
    能提供其中一种查询方式要的查询键，就能用同一个 Adapter 观测。
    查询逻辑确实依赖类型时，可在 fetch 里读 QuerySpec.type 兜底。
    """

    name: str                           # 上游名，写进 ObservableTarget.upstreams
    observed_points: frozenset[type[ObservedPoint]]  # 服务的观察点；返回的观测必须是所查观察点的观测类
    # 支持的查询方式，按优先级排列；每种是一组需要目标提供的查询键（对所服务的全部观察点通用）。
    # 目标能提供其中任意一组（这些查询键都有值），就能用这个上游观测它；采用第一组满足的。
    # 例如 (frozenset({Icao24}), frozenset({Mmsi}))：有 ICAO 地址的按它查，有 MMSI 的按它查——
    # Adapter 不需要认识目标类型，也不需要知道目标的字段名。
    query_key_sets: tuple[frozenset[type[QueryKey]], ...]

    @abstractmethod
    def fetch(
        self, spec: QuerySpec, query: Query, since: datetime | None
    ) -> Sequence[FetchedRecord]:
        """拉取 since 之后（不含）的记录。

        spec：查的是哪个观察点（服务多个观察点时按它分支）；query：这次采用的查询方式及取值
        （已按查询键校验，是目标信息的唯一来源）；
        since：这个上游的游标，首次采集为 None。
        """
        ...


def check_adapter(adapter: Adapter) -> None:
    """注册时检查子类把类属性都声明了，且至少服务一个观察点、支持一种查询方式；不合格抛 TypeError。"""
    missing = [
        attr for attr in ("name", "observed_points", "query_key_sets") if not hasattr(adapter, attr)
    ]
    if missing:
        raise TypeError(f"{type(adapter).__name__} must set {', '.join(missing)}")
    if not adapter.observed_points:
        raise TypeError(f"{adapter.name}: observed_points needs at least one observed point")
    if not adapter.query_key_sets or not all(adapter.query_key_sets):
        raise TypeError(f"{adapter.name}: query_key_sets needs at least one non-empty set")
