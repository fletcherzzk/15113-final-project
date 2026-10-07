import math
import random

import pytest

from lab.simulation import (
    POLICIES, StructuralError, Task, ValidationError, analyze_graph,
    generate_dc, generate_map, parse_configuration, run_experiment, simulate,
)


def map_config(durations=None, processors=2, policy="longest"):
    return {"form": "map", "parameters": {"durations": durations or [3, 3, 2, 2, 2]},
            "processors": processors, "policy": policy}


def assert_schedule(tasks, processors, result):
    timeline = result["timeline"]
    assignments = {entry["task_id"]: entry for entry in timeline}
    assert len(assignments) == len(timeline) == len(tasks)
    for task in tasks:
        entry = assignments[task.id]
        assert 1 <= entry["processor_id"] <= processors
        assert entry["start"] >= 0
        assert entry["end"] - entry["start"] == task.duration
        assert all(assignments[dep]["end"] <= entry["start"] for dep in task.dependencies)
    end = result["metrics"]["makespan"]
    assert end == max(entry["end"] for entry in timeline)
    for processor in range(1, processors + 1):
        intervals = sorted((e["start"], e["end"]) for e in timeline if e["processor_id"] == processor)
        assert all(first[1] <= second[0] for first, second in zip(intervals, intervals[1:]))
        # Computation and recorded idle intervals tile the complete common axis.
        idle = [(e["start"], e["end"]) for e in result["idle_intervals"] if e["processor_id"] == processor]
        tiled = sorted(intervals + idle)
        assert tiled[0][0] == 0 and tiled[-1][1] == end
        assert all(first[1] == second[0] for first, second in zip(tiled, tiled[1:]))
    assert end >= result["metrics"]["lower_bound"]
    assert 0 < result["metrics"]["utilization"] <= 1
    if processors == 1:
        assert end == sum(task.duration for task in tasks)


def test_spec_nonuniform_example_and_known_better_arrangement():
    experiment = run_experiment(map_config())
    for policy in POLICIES:
        assert experiment["comparisons"][policy]["metrics"]["makespan"] == 7
    assert experiment["comparisons"]["longest"]["timeline"] == [
        {"task_id": 1, "processor_id": 1, "start": 0, "end": 3},
        {"task_id": 2, "processor_id": 2, "start": 0, "end": 3},
        {"task_id": 3, "processor_id": 1, "start": 3, "end": 5},
        {"task_id": 4, "processor_id": 2, "start": 3, "end": 5},
        {"task_id": 5, "processor_id": 1, "start": 5, "end": 7},
    ]
    assert experiment["results"]["metrics"]["lower_bound"] == 6
    # A manually checked partition attains six; the heuristics do not.
    assert sum([3, 3]) == sum([2, 2, 2]) == 6


@pytest.mark.parametrize("count", [2, 5, 8, 16])
@pytest.mark.parametrize("duration", [1, 3, 20])
def test_uniform_map_formula(count, duration):
    tasks = generate_map([duration] * count)
    for processors in range(1, count):
        for policy in POLICIES:
            result = simulate(tasks, processors, policy)
            assert result["metrics"]["makespan"] == math.ceil(count / processors) * duration
            assert_schedule(tasks, processors, result)


def test_small_dc_manual_schedule():
    tasks = generate_dc(2, 2, 1, 2, 3, 4)
    assert [t.to_dict() for t in tasks] == [
        {"id": 1, "type": "split", "duration": 2, "dependencies": [], "size": 2, "depth": 0},
        {"id": 2, "type": "base", "duration": 3, "dependencies": [1], "size": 1, "depth": 1},
        {"id": 3, "type": "base", "duration": 3, "dependencies": [1], "size": 1, "depth": 1},
        {"id": 4, "type": "combine", "duration": 4, "dependencies": [2, 3], "size": 2, "depth": 0},
    ]
    result = simulate(tasks, 2, "fixed")
    assert result["metrics"] == {"work": 12, "span": 9, "average_parallelism": 12 / 9,
                                 "makespan": 9, "speedup": 12 / 9, "utilization": 12 / 18,
                                 "lower_bound": 9}
    assert result["timeline"][-1] == {"task_id": 4, "processor_id": 1, "start": 5, "end": 9}
    assert_schedule(tasks, 2, result)


def test_balanced_dc_breadth_first_ids_and_policy_ties():
    tasks = generate_dc(8, 2, 1, 1, 1, 1)
    assert [task.type for task in tasks] == ["split"] * 7 + ["base"] * 8 + ["combine"] * 7
    assert [task.dependencies for task in tasks] == [
        (), (1,), (1,), (2,), (2,), (3,), (3,),
        (4,), (4,), (5,), (5,), (6,), (6,), (7,), (7,),
        (8, 9), (10, 11), (12, 13), (14, 15), (16, 17), (18, 19), (20, 21),
    ]
    for policy in POLICIES:
        result = simulate(tasks, 1, policy)
        # Equal duration/rank siblings break ties with their new IDs.
        assert [entry["task_id"] for entry in result["timeline"]] == list(range(1, 23))


def test_unbalanced_dc_numbers_combines_by_dependency_level():
    tasks = generate_dc(5, 2, 1, 1, 3, 1)
    assert [(task.type, task.size, task.dependencies) for task in tasks] == [
        ("split", 5, ()), ("split", 2, (1,)), ("split", 3, (1,)),
        ("base", 1, (2,)), ("base", 1, (2,)), ("base", 1, (3,)), ("split", 2, (3,)),
        ("combine", 2, (4, 5)), ("base", 1, (7,)), ("base", 1, (7,)),
        ("combine", 2, (9, 10)), ("combine", 3, (6, 11)), ("combine", 5, (8, 12)),
    ]
    assert [entry["task_id"] for entry in simulate(tasks, 1, "fixed")["timeline"]] == list(range(1, 14))


@pytest.mark.parametrize("n,k,children", [(8, 3, [3, 5]), (5, 2, [2, 3]), (3, 4, [1, 2])])
def test_split_rounding(n, k, children):
    tasks = generate_dc(n, k, n - 1, 1, 1, 1)
    assert [task.size for task in tasks if task.dependencies == (1,)] == children


def test_all_supported_dc_shapes_and_scheduling_invariants():
    for n in range(2, 9):
        for k in range(2, 9):
            for b in range(1, n):
                tasks = generate_dc(n, k, b, 2, 5, 3)
                assert len(tasks) <= 22
                assert [task.id for task in tasks] == list(range(1, len(tasks) + 1))
                levels = {}
                for task in tasks:
                    assert all(dep < task.id for dep in task.dependencies)
                    levels[task.id] = 1 + max((levels[dep] for dep in task.dependencies), default=-1)
                assert list(levels.values()) == sorted(levels.values())
                by_id = {task.id: task for task in tasks}
                assert len([task for task in tasks if task.type == "base"]) <= n
                for task in tasks:
                    if task.type == "split":
                        children = [child for child in tasks if child.dependencies == (task.id,)]
                        assert len(children) == 2
                        assert sum(child.size for child in children) == task.size
                        assert all(0 < child.size < task.size for child in children)
                    elif task.type == "combine":
                        assert len(task.dependencies) == 2
                        assert all(by_id[dep].type in ("combine", "base") for dep in task.dependencies)
                for processors in {1, 2, len(tasks) - 1}:
                    for policy in POLICIES:
                        result = simulate(tasks, processors, policy)
                        assert_schedule(tasks, processors, result)
                        assert result == simulate(tasks, processors, policy)
    maximum = generate_dc(8, 2, 1, 1, 1, 1)
    assert len(maximum) == 22
    assert [sum(task.type == kind for task in maximum) for kind in ("base", "split", "combine")] == [8, 7, 7]


def test_random_maps_and_critical_longest_equivalence():
    randomizer = random.Random(15113)
    for _ in range(80):
        count = randomizer.randint(2, 16)
        tasks = generate_map([randomizer.randint(1, 20) for _ in range(count)])
        processors = randomizer.randint(1, count - 1)
        results = {policy: simulate(tasks, processors, policy) for policy in POLICIES}
        for result in results.values():
            assert_schedule(tasks, processors, result)
        assert results["longest"]["timeline"] == results["critical"]["timeline"]


def test_ready_policy_priorities_and_processor_ties():
    tasks = [Task(1, "map", 1), Task(2, "map", 5), Task(3, "map", 2)]
    assert [e["task_id"] for e in simulate(tasks, 1, "fixed")["timeline"]] == [1, 2, 3]
    assert [e["task_id"] for e in simulate(tasks, 1, "longest")["timeline"]] == [2, 3, 1]
    tasks = [Task(1, "split", 1), Task(2, "split", 3), Task(3, "base", 10, (1,)), Task(4, "base", 1, (2,))]
    assert simulate(tasks, 1, "longest")["timeline"][0]["task_id"] == 2
    assert simulate(tasks, 1, "critical")["timeline"][0]["task_id"] == 1
    assert analyze_graph(tasks) == {4: 1, 3: 10, 2: 4, 1: 11}
    tied = simulate(generate_map([2] * 12), 2, "fixed")["timeline"]
    assert [e["task_id"] for e in tied] == list(range(1, 13))
    assert [e["processor_id"] for e in tied] == [1, 2] * 6


def test_simultaneous_completions_before_new_assignments():
    tasks = [Task(1, "base", 2), Task(2, "base", 2), Task(3, "combine", 1, (1, 2)), Task(4, "base", 4, (1,))]
    result = simulate(tasks, 2, "fixed")
    assert result["timeline"][2:] == [
        {"task_id": 3, "processor_id": 1, "start": 2, "end": 3},
        {"task_id": 4, "processor_id": 2, "start": 2, "end": 6},
    ]


@pytest.mark.parametrize("tasks", [
    [Task(1, "base", 1, (2,)), Task(2, "base", 1, (1,))],
    [Task(1, "base", 1, (3,)), Task(2, "base", 1)],
    [Task(1, "base", 1), Task(1, "base", 1)],
    [Task(1, "base", 1, (2, 2)), Task(2, "base", 1)],
    [Task(1, "base", 0), Task(2, "base", 1)],
])
def test_structural_errors(tasks):
    with pytest.raises(StructuralError):
        simulate(tasks, 1, "fixed")


@pytest.mark.parametrize("durations", [[], [1], [1] * 17, [0, 1], [1, 21], [1.5, 2], [True, 2], "1,2", ["1", 2]])
def test_bad_maps(durations):
    with pytest.raises(ValidationError):
        generate_map(durations)


@pytest.mark.parametrize("args", [(1, 2, 1, 1, 1, 1), (9, 2, 1, 1, 1, 1), (8, 1, 1, 1, 1, 1), (8, 9, 1, 1, 1, 1), (8, 2, 0, 1, 1, 1), (8, 2, 8, 1, 1, 1), (8, 2, 1, 0, 1, 1), (8, 2, 1, 1, 21, 1), (8, 2, 1, 1, 1, 1.5)])
def test_bad_dc(args):
    with pytest.raises(ValidationError):
        generate_dc(*args)


@pytest.mark.parametrize("processors", [0, 5, -1, 1.5, True, "2", None])
def test_bad_processors(processors):
    with pytest.raises(ValidationError):
        parse_configuration(map_config(processors=processors))


@pytest.mark.parametrize("config", [None, [], {}, {"form": "dag", "parameters": {}}, {"form": "map", "parameters": []}, {**map_config(), "policy": "optimal"}])
def test_bad_configurations(config):
    with pytest.raises(ValidationError):
        parse_configuration(config)
