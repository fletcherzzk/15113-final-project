"""Deterministic DAG generation and nonpreemptive discrete-event scheduling.

Task IDs are numeric preorder IDs. A recursive call allocates its split,
then the complete left and right subgraphs, then its combine task.
"""

from dataclasses import asdict, dataclass
import heapq
from typing import Any

SIMULATOR_VERSION = "1.0.0"
POLICIES = ("fixed", "longest", "critical")


class ValidationError(ValueError):
    """A configuration is outside the supported model."""


class StructuralError(ValueError):
    """A graph contains invalid dependencies or a cycle."""


@dataclass(frozen=True)
class Task:
    id: int
    type: str
    duration: int
    dependencies: tuple[int, ...] = ()
    size: int | None = None
    depth: int = 0

    def to_dict(self):
        value = asdict(self)
        value["dependencies"] = list(self.dependencies)
        return value


def integer(value, name, low, high):
    # bool is an int subclass, but is never a valid numeric input here.
    if type(value) is not int or not low <= value <= high:
        raise ValidationError(f"{name} must be an integer from {low} to {high}.")
    return value


def generate_map(durations):
    if not isinstance(durations, list) or not 2 <= len(durations) <= 16:
        raise ValidationError("Map requires 2–16 task durations.")
    return [Task(i + 1, "map", integer(d, f"Task {i + 1} duration", 1, 20))
            for i, d in enumerate(durations)]


def generate_dc(n, k, b, split, base, combine):
    integer(n, "Problem size n", 2, 8)
    integer(k, "Split parameter k", 2, 8)
    integer(b, "Base threshold b", 1, n - 1)
    for name, duration in (("Split duration", split), ("Base duration", base),
                           ("Combine duration", combine)):
        integer(duration, name, 1, 20)
    tasks = []

    def add(kind, duration, deps, size, depth):
        task = Task(len(tasks) + 1, kind, duration, tuple(deps), size, depth)
        tasks.append(task)
        if len(tasks) > 22:
            raise ValidationError("D&C may generate at most 22 computation tasks.")
        return task.id

    def visit(size, deps, depth):
        if size <= b:
            return add("base", base, deps, size, depth)
        start = add("split", split, deps, size, depth)
        small = min((size + k - 1) // k, size // 2)
        left = visit(small, [start], depth + 1)
        right = visit(size - small, [start], depth + 1)
        return add("combine", combine, [left, right], size, depth)

    visit(n, [], 0)
    return tasks


def parse_configuration(raw: Any):
    if not isinstance(raw, dict):
        raise ValidationError("Configuration must be a JSON object.")
    form = raw.get("form")
    params = raw.get("parameters")
    if not isinstance(params, dict):
        raise ValidationError("Parameters must be a JSON object.")
    if form == "map":
        durations = params.get("durations")
        tasks = generate_map(durations)
        parameters = {"durations": durations.copy()}
    elif form == "dc":
        keys = ("n", "k", "b", "split_duration", "base_duration", "combine_duration")
        parameters = {key: params.get(key) for key in keys}
        tasks = generate_dc(*(parameters[key] for key in keys))
    else:
        raise ValidationError("Choose Map or Divide-and-Conquer.")
    processors = integer(raw.get("processors"), "Processor count P", 1, len(tasks) - 1)
    policy = raw.get("policy")
    if policy not in POLICIES:
        raise ValidationError("Policy must be fixed, longest, or critical.")
    return {"form": form, "parameters": parameters, "processors": processors,
            "policy": policy}, tasks


def analyze_graph(tasks):
    """Kahn topological order followed by reverse-order remaining-path ranks."""
    by_id = {task.id: task for task in tasks}
    if not tasks or len(by_id) != len(tasks):
        raise StructuralError("Task IDs must be unique and the graph nonempty.")
    successors = {task.id: [] for task in tasks}
    indegree = {}
    for task in tasks:
        if type(task.id) is not int or type(task.duration) is not int or task.duration <= 0:
            raise StructuralError("Task IDs and positive durations must be integers.")
        if len(set(task.dependencies)) != len(task.dependencies):
            raise StructuralError("Duplicate dependency.")
        indegree[task.id] = len(task.dependencies)
        for dep in task.dependencies:
            if dep not in by_id:
                raise StructuralError("Dependency refers to a missing task.")
            successors[dep].append(task.id)
    ready = [task_id for task_id, count in indegree.items() if count == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        task_id = heapq.heappop(ready)
        order.append(task_id)
        for child in successors[task_id]:
            indegree[child] -= 1
            if indegree[child] == 0:
                heapq.heappush(ready, child)
    if len(order) != len(tasks):
        raise StructuralError("Unfinished tasks have no running or ready tasks: dependency cycle.")
    ranks = {}
    for task_id in reversed(order):
        ranks[task_id] = by_id[task_id].duration + max(
            (ranks[child] for child in successors[task_id]), default=0)
    return ranks


def simulate(tasks, processors, policy):
    integer(processors, "Processor count P", 1, len(tasks) - 1)
    if policy not in POLICIES:
        raise ValidationError("Unknown policy.")
    ranks = analyze_graph(tasks)
    remaining = {task.id: task for task in tasks}
    completed = set()
    running = []  # (finish time, processor ID, task ID)
    available = list(range(1, processors + 1))
    timeline = []
    time = 0
    while remaining or running:
        # Release EVERY completion at this event before recomputing the ready set.
        while running and running[0][0] == time:
            _, processor, task_id = heapq.heappop(running)
            completed.add(task_id)
            heapq.heappush(available, processor)
        ready = [task for task in remaining.values()
                 if all(dep in completed for dep in task.dependencies)]
        priority = {"fixed": lambda t: (t.id,),
                    "longest": lambda t: (-t.duration, t.id),
                    "critical": lambda t: (-ranks[t.id], t.id)}[policy]
        ready.sort(key=priority)
        for task in ready[:len(available)]:
            processor = heapq.heappop(available)
            end = time + task.duration
            timeline.append({"task_id": task.id, "processor_id": processor,
                             "start": time, "end": end})
            heapq.heappush(running, (end, processor, task.id))
            del remaining[task.id]
        if running:
            time = running[0][0]
        elif remaining:
            raise StructuralError("Unfinished tasks have no running or ready tasks.")
    work = sum(task.duration for task in tasks)
    span = max(ranks.values())
    idle = []
    for processor in range(1, processors + 1):
        cursor = 0
        for entry in (e for e in timeline if e["processor_id"] == processor):
            if entry["start"] > cursor:
                idle.append({"processor_id": processor, "start": cursor, "end": entry["start"]})
            cursor = entry["end"]
        if cursor < time:
            idle.append({"processor_id": processor, "start": cursor, "end": time})
    return {"policy": policy, "timeline": timeline, "idle_intervals": idle,
            "metrics": {"work": work, "span": span, "average_parallelism": work / span,
                        "makespan": time, "speedup": work / time,
                        "utilization": work / (processors * time),
                        "lower_bound": max(work / processors, span)}}


def run_experiment(raw):
    config, tasks = parse_configuration(raw)
    comparisons = {policy: simulate(tasks, config["processors"], policy) for policy in POLICIES}
    ranks = analyze_graph(tasks)
    return {"configuration": config, "simulator_version": SIMULATOR_VERSION,
            "dag": [{**task.to_dict(), "rank": ranks[task.id]} for task in tasks],
            "results": comparisons[config["policy"]], "comparisons": comparisons}
