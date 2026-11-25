"""topk_check.first_near finds the first candidate within the distance of the label."""
import topk_check


def test_first_near():
    row = {"true_e": 0.0, "true_n": 0.0}
    top = [{"east": 100.0, "north": 0.0}, {"east": 30.0, "north": 30.0}, {"east": 1.0, "north": 1.0}]
    assert topk_check.first_near(row, top, 50.0) == 2
    assert topk_check.first_near(row, top, 10.0) == 3
    assert topk_check.first_near(row, top[:1], 50.0) == 0
