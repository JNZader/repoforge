"""Chapter prose must match the facts it was given."""

from repoforge.facts import FactItem
from repoforge.factuality import check_factuality, invented_claim_block, repair_invented_chapter


def _port(value: str) -> FactItem:
    return FactItem("port", value, "main.go", 1, "Go")


def _endpoint(value: str) -> FactItem:
    return FactItem("endpoint", value, "app/main.py", 1, "Python")


def _table(value: str) -> FactItem:
    return FactItem("db_table", value, "models.py", 1, "Python")


def _env(value: str) -> FactItem:
    return FactItem("env_var", value, "config.py", 1, "Python")


def test_invented_port_fails_when_only_fact_is_7437():
    report = check_factuality("The server listens on port 8080.", [_port("7437")])
    assert report.ok is False
    assert "port:8080" in report.invented
    assert "port:7437" in report.missing


def test_real_port_passes():
    report = check_factuality("The server listens on port 7437.", [_port("7437")])
    assert report.ok is True
    assert report.invented == ()
    assert report.missing == ()


def test_real_port_plus_invented_port_fails():
    report = check_factuality(
        "Listens on port 7437, or port 8080 in development.",
        [_port("7437")],
    )
    assert "port:8080" in report.invented
    assert "port:7437" not in report.missing


def test_port_digits_do_not_match_inside_a_longer_number():
    report = check_factuality("The build id is 18080 and it listens on port 7437.", [_port("7437")])
    assert report.ok is True


def test_bare_integer_is_not_a_port_claim():
    report = check_factuality("See line 120. The server listens on port 7437.", [_port("7437")])
    assert report.ok is True


def test_invented_endpoint_fails():
    report = check_factuality(
        "Call POST /admin to sign in. GET /health is the probe.",
        [_endpoint("GET /health")],
    )
    assert "endpoint:POST /admin" in report.invented
    assert "endpoint:GET /health" not in report.missing


def test_real_endpoint_passes():
    report = check_factuality("GET /health returns ok.", [_endpoint("GET /health")])
    assert report.ok is True


def test_invented_table_fails_and_named_table_passes():
    invented = check_factuality("The table accounts holds rows.", [_table("users")])
    assert "db_table:accounts" in invented.invented
    assert "db_table:users" in invented.missing

    present = check_factuality("The table users holds rows.", [_table("users")])
    assert present.ok is True


def test_invented_env_var_fails_and_named_env_passes():
    invented = check_factuality("Set DATABASE_URL before boot.", [_env("ENGRAM_PORT")])
    assert "env_var:DATABASE_URL" in invented.invented
    assert "env_var:ENGRAM_PORT" in invented.missing

    present = check_factuality("Set ENGRAM_PORT before boot.", [_env("ENGRAM_PORT")])
    assert present.ok is True


def test_no_facts_and_no_claims_passes():
    assert check_factuality("This chapter explains the module layout.", []).ok is True


def test_no_facts_and_a_port_claim_is_invented():
    report = check_factuality("The server listens on port 8080.", [])
    assert report.invented == ("port:8080",)
    assert report.missing == ()


def test_invented_port_blocks_the_write_and_a_real_port_does_not():
    facts = [_port("7437")]
    assert invented_claim_block("The server listens on port 8080.", facts) == "factuality: port:8080"
    assert invented_claim_block("The server listens on port 7437.", facts) is None


def test_omitted_fact_does_not_block_the_write():
    assert invented_claim_block("This chapter explains the module layout.", [_port("7437")]) is None


class _FakeLLM:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls = 0

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls += 1
        return self.reply


def test_one_repair_with_the_real_port_is_writable():
    llm = _FakeLLM("The server listens on port 7437.")
    text, error = repair_invented_chapter(
        llm, "The server listens on port 8080.", [_port("7437")],
    )
    assert error is None
    assert text == "The server listens on port 7437."
    assert llm.calls == 1


def test_one_repair_that_still_invents_is_not_writable():
    llm = _FakeLLM("The server listens on port 8080.")
    _text, error = repair_invented_chapter(
        llm, "The server listens on port 8080.", [_port("7437")],
    )
    assert error is not None
    assert "port:8080" in error
    assert llm.calls == 1


def test_clean_chapter_does_not_call_the_repair_model():
    llm = _FakeLLM("unused")
    text, error = repair_invented_chapter(
        llm, "The server listens on port 7437.", [_port("7437")],
    )
    assert error is None
    assert text == "The server listens on port 7437."
    assert llm.calls == 0


def test_harness_appends_factuality_score_when_facts_are_passed():
    from eval.harness import run_scenario, score_factuality

    passed = score_factuality("The server listens on port 7437.", [_port("7437")])
    assert passed.dimension == "factuality"
    assert passed.score == 1.0

    failed = score_factuality("The server listens on port 8080.", [_port("7437")])
    assert failed.score == 0.0
    assert any("port:8080" in item for item in failed.failed)

    result = run_scenario("fastapi_crud", llm=None, verbose=False, facts=[_port("7437")])
    factuality = [score for score in result.scores if score.dimension == "factuality"]
    assert len(factuality) == 1
    assert factuality[0].score == 0.0
