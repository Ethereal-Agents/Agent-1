import json
import os
from unittest import mock
from eval.dataset import load_swe_bench, filter_by_tier

@mock.patch("datasets.load_dataset")
def test_load_swe_bench(mock_load_dataset):
    mock_load_dataset.return_value = [{"instance_id": "a"}]
    res = load_swe_bench("dataset", "test")
    assert res == [{"instance_id": "a"}]

def test_filter_by_tier(tmp_path):
    instances = [{"instance_id": "a"}, {"instance_id": "b"}, {"instance_id": "c"}]
    tier_file = tmp_path / "tier.json"
    tier_file.write_text(json.dumps({"instance_ids": ["a", "b"]}))
    res = filter_by_tier(instances, str(tier_file))
    assert len(res) == 2
    assert "c" not in [i["instance_id"] for i in res]
