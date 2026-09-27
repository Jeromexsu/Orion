from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import datetime
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, SerializeAsAny

from core.observation import Observation, ObservedPoint
from core.target import QueryKey

Query = dict[type[QueryKey], Any]
"""这次查询：查询键 → 取值，如 {Icao24: "780a3b"}。由 collector 按上游挑出的查询方式组装。"""


class FetchedRecord(BaseModel):
    """UpstreamAdapter 从上游拿到的一条记录：观测实例 + 来源信息。

    observation 由 UpstreamAdapter 直接构造成观察点的观测类（如 PositionObservation），字段写错在 UpstreamAdapter 里当场报错；
    collector 只检查它的类型是否与上游服务的观察点一致。
    """

    model_config = ConfigDict(frozen=True)

    observation: SerializeAsAny[Observation]
    occurred_at: datetime
    source_id: str              # 全局唯一，去重用，如 "adsb#881"
    raw: dict[str, Any] | None = None   # 上游原始响应，便于排查


class UpstreamAdapter(ABC):
    """上游基类。一个上游（数据提供方，如 OpenSky）一个子类，放在 plugins/upstream_adapters/ 下：

        @upstream_adapter(observed_points=[Position], query_key_sets=[{Icao24}])
        class OpenSkyAdapter(UpstreamAdapter):
            def fetch(self, observed_point, query, since): ...

    name（上游名）默认是类名去掉 Adapter 后缀、首字母小写（OpenSkyAdapter → "openSky"）。
    一个上游可以服务多个观察点：fetch 按 observed_point 分支（比较类：observed_point is Position），
    返回对应观察点的观测；
    游标、订阅、路由都按（可观测目标, 上游）组织，可观测目标里已带观察点，所以互不干扰。
    UpstreamAdapter 不关心目标类型，只关心观察点（输出契约）和查询键（输入契约）——不同目标类型只要
    能提供其中一种查询方式要的查询键，就能用同一个 UpstreamAdapter 观测。目标的信息只经查询键传进来。
    """

    name: str                           # 上游名，写进 ObservableTarget.upstreams
    observed_points: frozenset[type[ObservedPoint]]  # 服务的观察点；返回的观测必须是所查观察点的观测类
    # 支持的查询方式，按优先级排列；每种是一组需要目标提供的查询键（对所服务的全部观察点通用）。
    # 目标能提供其中任意一组（这些查询键都有值），就能用这个上游观测它；采用第一组满足的。
    # 例如 (frozenset({Icao24}), frozenset({Mmsi}))：有 ICAO 地址的按它查，有 MMSI 的按它查——
    # UpstreamAdapter 不需要认识目标类型，也不需要知道目标的字段名。
    query_key_sets: tuple[frozenset[type[QueryKey]], ...]

    def choose_query(self, provided: Mapping[type[QueryKey], Any]) -> Query | None:
        """按优先级挑出第一种能满足的查询方式，返回这次的查询（查询键 → 取值）；都不满足返回 None。

        provided 是目标能提供的查询键及取值（Target.query_values()）——只交查询键，不交目标本身。
        判断可用上游和实际采集都用它，保证两处一致。基类实现，插件不要覆盖。
        """
        for keys in self.query_key_sets:
            if keys <= provided.keys():
                return {k: provided[k] for k in keys}
        return None

    @abstractmethod
    def fetch(
        self, observed_point: type[ObservedPoint], query: Query, since: datetime | None
    ) -> Sequence[FetchedRecord]:
        """拉取 since 之后（不含）的记录。

        observed_point：查哪个观察点（在 observed_points 里；服务多个观察点时按它分支）；
        query：凭什么查——这次采用的查询方式及取值（已按查询键校验，是目标信息的唯一来源）；
        since：从哪儿开始查——这个上游的游标，首次采集为 None。
        """
        ...


A = TypeVar("A", bound=UpstreamAdapter)


def upstream_adapter(
    *,
    observed_points: Iterable[type[ObservedPoint]],
    query_key_sets: Iterable[Iterable[type[QueryKey]]],
    name: str | None = None,
) -> Callable[[type[A]], type[A]]:
    """Declare an upstream adapter.

    Args:
        observed_points: Observed points it serves (at least one).
        query_key_sets: Query ways it supports, in priority order; each is a set of
            query keys used together (at least one non-empty set).
        name: Upstream name, used in templates and for subscriptions and cursors.
            Defaults to the class name without an "Adapter" suffix, first letter
            lowered (OpenSkyAdapter -> "openSky").

    Raises:
        TypeError: If the declaration is incomplete.
    """

    def decorate(cls: type[A]) -> type[A]:
        cls.name = name if name is not None else _default_name(cls.__name__)
        cls.observed_points = frozenset(observed_points)
        cls.query_key_sets = tuple(frozenset(keys) for keys in query_key_sets)
        validate_declaration(cls.__name__, cls.name, cls.observed_points, cls.query_key_sets)
        return cls

    return decorate


def validate_declaration(
    class_name: str,
    name: str,
    observed_points: frozenset[type[ObservedPoint]],
    query_key_sets: tuple[frozenset[type[QueryKey]], ...],
) -> None:
    """Raise TypeError if a declaration is incomplete; shared by the decorator and the registry."""
    if not name:
        raise TypeError(f"{class_name}: upstream name must not be empty")
    if not observed_points:
        raise TypeError(f"{name}: observed_points needs at least one observed point")
    if not query_key_sets or not all(query_key_sets):
        raise TypeError(f"{name}: query_key_sets needs at least one non-empty set")


def _default_name(class_name: str) -> str:
    base = class_name.removesuffix("Adapter") or class_name
    return base[:1].lower() + base[1:]
