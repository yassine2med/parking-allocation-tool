import pytest

from parkalloc.cli import main
from parkalloc.core import DataError, Request, Space, allocate, load_requests, load_spaces, score


def req(name, need="standard", carpool=False, weeks=0, miles=0.0):
    return Request(name, need, carpool, weeks, miles)


def test_score_formula():
    assert score(req("a", carpool=True, weeks=2, miles=20)) == 2 * 2 + 3 + 2


def test_commute_points_are_capped():
    assert score(req("a", miles=500)) == 5


def test_more_weeks_waiting_wins():
    spaces = [Space("S-1", "standard", "N")]
    got, wait = allocate(spaces, [req("low", weeks=1), req("high", weeks=5)])
    assert got[0][0].employee == "high"
    assert wait[0].employee == "low"


def test_accessible_only_gets_accessible():
    spaces = [Space("S-1", "standard", "N")]
    got, wait = allocate(spaces, [req("a", need="accessible")])
    assert got == [] and len(wait) == 1


def test_ev_falls_back_to_standard():
    spaces = [Space("S-1", "standard", "N")]
    got, wait = allocate(spaces, [req("a", need="ev")])
    assert got[0][1].space_id == "S-1" and wait == []


def test_standard_never_takes_ev_space():
    spaces = [Space("E-1", "ev", "N")]
    got, wait = allocate(spaces, [req("a")])
    assert got == [] and len(wait) == 1


def test_ev_users_get_ev_space_before_fallback():
    spaces = [Space("E-1", "ev", "N"), Space("S-1", "standard", "N")]
    got, _ = allocate(spaces, [req("a", need="ev")])
    assert got[0][1].space_id == "E-1"


def test_same_seed_same_result():
    spaces = [Space("S-1", "standard", "N")]
    reqs = [req("a"), req("b"), req("c")]
    first = allocate(spaces, reqs, seed=7)[0][0][0].employee
    again = allocate(spaces, reqs, seed=7)[0][0][0].employee
    assert first == again


def test_tie_break_depends_on_seed():
    spaces = [Space("S-1", "standard", "N")]
    reqs = [req(c) for c in "abcdefgh"]
    winners = {allocate(spaces, reqs, seed=s)[0][0][0].employee for s in range(30)}
    assert len(winners) > 1


def test_no_space_used_twice():
    spaces = [Space(f"S-{i}", "standard", "N") for i in range(3)]
    got, wait = allocate(spaces, [req(str(i)) for i in range(5)])
    assert len({s.space_id for _, s in got}) == 3 and len(wait) == 2


def test_load_examples():
    assert len(load_spaces("examples/spaces.csv")) == 8
    assert len(load_requests("examples/requests.csv")) == 11


def test_bad_need_rejected(tmp_path):
    p = tmp_path / "r.csv"
    p.write_text("employee,need,carpool,weeks_waiting,commute_miles\nA,vip,no,0,1\n")
    with pytest.raises(DataError, match="need 'vip'"):
        load_requests(str(p))


def test_duplicate_space_rejected(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text("space_id,type,zone\nA,standard,N\nA,standard,N\n")
    with pytest.raises(DataError, match="duplicate"):
        load_spaces(str(p))


def test_cli_exit_codes(capsys):
    assert main(["allocate", "examples/spaces.csv", "examples/requests.csv"]) == 1
    assert "WAITLIST" in capsys.readouterr().out
    assert main(["allocate", "nope.csv", "examples/requests.csv"]) == 2


def test_cli_writes_csv(tmp_path):
    out = tmp_path / "a.csv"
    main(["allocate", "examples/spaces.csv", "examples/requests.csv", "--out", str(out)])
    assert out.read_text().splitlines()[0] == "employee,need,score,space_id"
