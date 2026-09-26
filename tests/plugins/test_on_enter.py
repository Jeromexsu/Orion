from plugins.condition_engine.on_enter import point_in_polygon

SQUARE = [(0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0)]


def test_point_in_polygon() -> None:
    assert point_in_polygon((5, 5), SQUARE)
    assert not point_in_polygon((15, 5), SQUARE)
    assert not point_in_polygon((5, -1), SQUARE)
