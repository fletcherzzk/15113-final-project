from concurrent.futures import ThreadPoolExecutor
import json

import pytest
from werkzeug.security import generate_password_hash

from lab.simulation import SIMULATOR_VERSION, run_experiment
from lab.storage import ConflictError, EventStore, StorageError


CONFIG = {"form": "dc", "parameters": {"n": 8, "k": 3, "b": 1, "split_duration": 1, "base_duration": 3, "combine_duration": 2}, "processors": 3, "policy": "critical"}


def test_concurrent_appends_from_distinct_store_instances(tmp_path):
    path = tmp_path / "records.jsonl"
    store = EventStore(path)
    user = store.create_user("alice", generate_password_hash("password123"))
    experiment = run_experiment(CONFIG)
    def save(index):
        return EventStore(path).create_experiment(user["id"], f"Experiment {index}", experiment)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(save, range(18)))
    assert len({result["id"] for result in results}) == 18
    assert len(EventStore(path).list_experiments(user["id"])) == 18
    assert len(path.read_text().splitlines()) == 19
    assert path.read_bytes().endswith(b"\n")


def test_concurrent_registration_uniqueness(tmp_path):
    path = tmp_path / "records.jsonl"
    password_hash = generate_password_hash("password123")
    def register(_):
        try:
            EventStore(path).create_user("Alice", password_hash)
            return "created"
        except ConflictError:
            return "conflict"
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(register, range(6)))
    assert results.count("created") == 1
    assert len(path.read_text().splitlines()) == 1


@pytest.mark.parametrize("corrupt", ['{"schema":1', '{bad}\n', '{"schema":99}\n', '[]\n'])
def test_corruption_fails_closed_and_preserves_file(tmp_path, corrupt):
    path = tmp_path / "records.jsonl"
    path.write_text(corrupt)
    store = EventStore(path)
    with pytest.raises(StorageError):
        store.find_user("alice")
    with pytest.raises(StorageError):
        store.create_user("alice", generate_password_hash("password123"))
    assert path.read_text() == corrupt


def test_tampered_stored_results_rejected(tmp_path):
    path = tmp_path / "records.jsonl"
    store = EventStore(path)
    user = store.create_user("alice", generate_password_hash("password123"))
    store.create_experiment(user["id"], "Original", run_experiment(CONFIG))
    records = [json.loads(line) for line in path.read_text().splitlines()]
    records[1]["data"]["experiment"]["comparisons"]["fixed"]["timeline"][0]["end"] += 1
    path.write_text("".join(json.dumps(record) + "\n" for record in records))
    with pytest.raises(StorageError):
        store.list_experiments(user["id"])


@pytest.mark.parametrize("form", ["map", "dc"])
def test_legacy_saves_load_with_current_ids_without_rewriting_log(tmp_path, form):
    path = tmp_path / "records.jsonl"
    store = EventStore(path)
    user = store.create_user("alice", generate_password_hash("password123"))
    config = CONFIG if form == "dc" else {
        "form": "map", "parameters": {"durations": [2, 5, 3]}, "processors": 2, "policy": "fixed",
    }
    legacy = run_experiment(config, simulator_version="1.0.0")
    saved = store.create_experiment(user["id"], "Legacy", legacy)
    original = path.read_bytes()
    restored = EventStore(path).get_experiment(user["id"], saved["id"])
    assert restored["simulator_version"] == SIMULATOR_VERSION
    assert restored["experiment"] == run_experiment(config)
    assert path.read_bytes() == original
    assert store.list_experiments(user["id"])[0] == restored
    store.rename_experiment(user["id"], saved["id"], "Renamed")
    assert store.get_experiment(user["id"], saved["id"])["name"] == "Renamed"
    assert path.read_bytes().startswith(original)
    store.create_experiment(user["id"], "New", run_experiment(config))
    store.delete_experiment(user["id"], saved["id"])
    assert [record["name"] for record in store.list_experiments(user["id"])] == ["New"]


def test_tampered_legacy_save_is_rejected_before_upgrade(tmp_path):
    path = tmp_path / "records.jsonl"
    store = EventStore(path)
    user = store.create_user("alice", generate_password_hash("password123"))
    store.create_experiment(user["id"], "Legacy", run_experiment(CONFIG, simulator_version="1.0.0"))
    records = [json.loads(line) for line in path.read_text().splitlines()]
    records[1]["data"]["experiment"]["dag"][1]["dependencies"] = []
    path.write_text("".join(json.dumps(record) + "\n" for record in records))
    original = path.read_bytes()
    with pytest.raises(StorageError):
        store.get_experiment(user["id"], records[1]["data"]["id"])
    assert path.read_bytes() == original
