"""Append-only JSONL event storage, protected across threads AND processes.

The separate lock file guards the entire read/modify/append transaction. No
event is overwritten on rename/delete. Replay fails closed on corrupt data.
"""

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import threading
from uuid import uuid4

import portalocker

from .simulation import SIMULATOR_VERSION, analyze_graph, parse_configuration


class StorageError(RuntimeError):
    pass


class ConflictError(ValueError):
    pass


class NotFoundError(LookupError):
    pass


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def experiment_name(value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 80:
        raise ValueError("Experiment name must contain 1–80 characters.")
    if any(ord(char) < 32 for char in value):
        raise ValueError("Experiment name cannot contain control characters.")
    return value.strip()


class EventStore:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = str(self.path) + ".lock"
        self.thread_lock = threading.RLock()

    @contextmanager
    def transaction(self):
        try:
            with self.thread_lock, portalocker.Lock(self.lock_path, timeout=10):
                yield self._read()
        except (OSError, portalocker.exceptions.LockException) as error:
            raise StorageError("The storage file is temporarily unavailable.") from error

    def _read(self):
        users, experiments = {}, {}
        if not self.path.exists():
            return users, experiments
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, 1):
                    if not line.endswith("\n"):
                        raise ValueError("Incomplete record")
                    record = json.loads(line)
                    if not isinstance(record, dict) or record.get("schema") != 1:
                        raise ValueError("Unknown record schema")
                    if not isinstance(record.get("at"), str):
                        raise ValueError("Missing event timestamp")
                    datetime.fromisoformat(record["at"])
                    kind, data = record.get("event"), record.get("data")
                    if not isinstance(data, dict):
                        raise ValueError("Missing record data")
                    if kind == "user_created":
                        self._validate_user(data)
                        if data["id"] in users or any(
                            u["username_key"] == data["username_key"] for u in users.values()
                        ):
                            raise ValueError("Duplicate user")
                        users[data["id"]] = data
                    elif kind == "experiment_created":
                        self._validate_experiment(data, users)
                        if data["id"] in experiments:
                            raise ValueError("Duplicate experiment")
                        experiments[data["id"]] = data
                    elif kind in ("experiment_renamed", "experiment_deleted"):
                        saved = experiments.get(data.get("id"))
                        if saved is None or saved["owner_id"] != data.get("owner_id"):
                            raise ValueError("Invalid experiment update")
                        if kind == "experiment_renamed":
                            saved["name"] = experiment_name(data.get("name"))
                        else:
                            del experiments[data["id"]]
                    else:
                        raise ValueError("Unknown event type")
        except (ValueError, KeyError, TypeError, UnicodeError) as error:
            raise StorageError(f"Invalid storage record at line {line_number}; restore or repair the log.") from error
        return users, experiments

    @staticmethod
    def _validate_user(data):
        if not isinstance(data.get("id"), str) or not re.fullmatch(r"[a-f0-9]{32}", data["id"]):
            raise ValueError("Invalid user ID")
        username = data.get("username")
        if not isinstance(username, str) or not re.fullmatch(r"[A-Za-z0-9_]{3,30}", username):
            raise ValueError("Invalid username")
        if data.get("username_key") != username.lower():
            raise ValueError("Invalid username key")
        password_hash = data.get("password_hash")
        if not isinstance(password_hash, str) or not re.fullmatch(
            r"scrypt:32768:8:1\$[A-Za-z0-9]{16}\$[a-f0-9]{128}", password_hash
        ):
            raise ValueError("Invalid password hash")
        datetime.fromisoformat(data["created_at"])

    @staticmethod
    def _validate_experiment(data, users):
        if not isinstance(data.get("id"), str) or not re.fullmatch(r"[a-f0-9]{32}", data["id"]):
            raise ValueError("Invalid experiment ID")
        if data.get("owner_id") not in users:
            raise ValueError("Unknown experiment owner")
        experiment_name(data.get("name"))
        config, tasks = parse_configuration(data.get("configuration"))
        if config != data["configuration"]:
            raise ValueError("Invalid stored configuration")
        datetime.fromisoformat(data["created_at"])
        result = data.get("experiment")
        if not isinstance(result, dict) or result.get("configuration") != config:
            raise ValueError("Invalid stored experiment")
        if data.get("simulator_version") != SIMULATOR_VERSION or result.get("simulator_version") != SIMULATOR_VERSION:
            raise ValueError("Unsupported simulator version; migrate records before upgrading")
        dag = result.get("dag")
        if not isinstance(dag, list) or len(dag) != len(tasks):
            raise ValueError("Invalid stored DAG")
        ranks = analyze_graph(tasks)
        for stored, expected in zip(dag, tasks):
            if not isinstance(stored, dict) or any(stored.get(key) != value for key, value in expected.to_dict().items()):
                raise ValueError("Invalid stored DAG task")
            if stored.get("rank") != ranks[expected.id]:
                raise ValueError("Invalid stored critical-path rank")
        from .simulation import POLICIES, simulate
        comparisons = result.get("comparisons")
        if not isinstance(comparisons, dict) or set(comparisons) != set(POLICIES):
            raise ValueError("Invalid stored comparisons")
        # Version 1 uses the deterministic simulator as a strict record validator.
        for policy in POLICIES:
            if comparisons[policy] != simulate(tasks, config["processors"], policy):
                raise ValueError("Invalid stored schedule")
        if result.get("results") != comparisons[config["policy"]]:
            raise ValueError("Invalid selected result")

    def _append(self, event, data):
        record = {"schema": 1, "event": event, "at": timestamp(), "data": data}
        payload = json.dumps(record, ensure_ascii=True, separators=(",", ":"), allow_nan=False) + "\n"
        # Caller holds both locks. The newline is the record boundary.
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

    def find_user(self, username):
        with self.transaction() as (users, _):
            return next((deepcopy(u) for u in users.values() if u["username_key"] == username.lower()), None)

    def get_user(self, user_id):
        with self.transaction() as (users, _):
            return deepcopy(users.get(user_id))

    def create_user(self, username, password_hash):
        with self.transaction() as (users, _):
            if any(u["username_key"] == username.lower() for u in users.values()):
                raise ConflictError("That username is already registered.")
            user = {"id": uuid4().hex, "username": username, "username_key": username.lower(),
                    "password_hash": password_hash, "created_at": timestamp()}
            self._validate_user(user)
            self._append("user_created", user)
            return deepcopy(user)

    def create_experiment(self, owner_id, name, experiment):
        with self.transaction() as (users, _):
            saved = {"id": uuid4().hex, "owner_id": owner_id, "name": experiment_name(name),
                     "configuration": experiment["configuration"], "experiment": experiment,
                     "simulator_version": experiment["simulator_version"], "created_at": timestamp()}
            self._validate_experiment(saved, users)
            self._append("experiment_created", saved)
            return deepcopy(saved)

    def list_experiments(self, owner_id):
        with self.transaction() as (_, experiments):
            return sorted((deepcopy(e) for e in experiments.values() if e["owner_id"] == owner_id),
                          key=lambda e: (e["created_at"], e["id"]), reverse=True)

    @staticmethod
    def _owned(experiments, owner_id, experiment_id):
        saved = experiments.get(experiment_id)
        if saved is None or saved["owner_id"] != owner_id:
            raise NotFoundError("Experiment not found.")
        return saved

    def get_experiment(self, owner_id, experiment_id):
        with self.transaction() as (_, experiments):
            return deepcopy(self._owned(experiments, owner_id, experiment_id))

    def rename_experiment(self, owner_id, experiment_id, name):
        name = experiment_name(name)
        with self.transaction() as (_, experiments):
            saved = self._owned(experiments, owner_id, experiment_id)
            self._append("experiment_renamed", {"id": experiment_id, "owner_id": owner_id, "name": name})
            return {**saved, "name": name}

    def delete_experiment(self, owner_id, experiment_id):
        with self.transaction() as (_, experiments):
            self._owned(experiments, owner_id, experiment_id)
            self._append("experiment_deleted", {"id": experiment_id, "owner_id": owner_id})
