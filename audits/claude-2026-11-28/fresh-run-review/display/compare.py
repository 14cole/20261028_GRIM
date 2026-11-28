"""Compare the independently produced Qt reports. Exits nonzero on any output mismatch."""
from pathlib import Path
import argparse
import json

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("main", type=Path)
parser.add_argument("candidate", type=Path)
parser.add_argument("--one-pass", action="store_true")
args = parser.parse_args()
main, candidate = (json.loads(p.read_text()) for p in (args.main, args.candidate))
assert main["case"] == candidate["case"]
baseline, updated = main["results"], candidate["results"]
assert baseline.keys() == updated.keys()
for case, before in baseline.items():
    after = updated[case]
    if "presentation" in before:
        for key in ("values", "state", "reader_released_after_replacement"):
            assert before.get(key) == after.get(key), (case, key, before.get(key), after.get(key))
        metric = after["presentation"]
        if args.one_pass and after.get("expected_compact", True):
            assert metric["loads_per_frequency"] == [1], (case, metric)
            assert metric["verified_frequency_loads"] == metric["distinct_frequencies"]
        print(case, before["values"]["rows"], before["values"]["cells"],
              before["presentation"]["verified_frequency_loads"], metric["verified_frequency_loads"])
    elif case == "corrupt_after_index":
        assert before["blocked"] and after["blocked"]
        assert all("7 GHz" in message for message in before["messages"] + after["messages"])
        assert after["previous_result_kept"]
        assert after["previous_valid_record_readable_after_error"]
        print(case, "candidate rejected corruption and retained previous view")
    elif case == "retry_after_disk_repair":
        assert after["repaired_without_reopen"] and not after["errors"], after
        print(case, "baseline", before["repaired_without_reopen"], "candidate", after["repaired_without_reopen"])
    else:
        assert before == after, (case, before, after)
        print(case, "match")
