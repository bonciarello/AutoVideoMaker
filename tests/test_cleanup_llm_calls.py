import json
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from cleanup_llm import FALLBACK_BETA, WindowRejected, ask_claude, review_with_claude
from cleanup_rules import Candidate
from helpers import make_words


class FakeMessages:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


class FakeClient:
    def __init__(self, replies):
        self.beta = SimpleNamespace(messages=FakeMessages(replies))


def _reply(data, stop_reason="end_turn"):
    return SimpleNamespace(stop_reason=stop_reason,
                           content=[SimpleNamespace(type="text", text=json.dumps(data))])


def test_ask_claude_sends_structured_output_request_with_fallback():
    client = FakeClient([_reply({"verdicts": [], "cuts": []})])
    assert ask_claude(client, "testo del blocco") == {"verdicts": [], "cuts": []}
    call = client.beta.messages.calls[0]
    assert call["model"] == "claude-opus-5"
    assert call["max_tokens"] == 16000
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert call["betas"] == [FALLBACK_BETA]
    assert call["fallbacks"] == "default"
    assert call["messages"] == [{"role": "user", "content": "testo del blocco"}]
    assert "thinking" not in call


@pytest.mark.parametrize("reason", ["refusal", "max_tokens"])
def test_ask_claude_rejects_refusal_and_truncation(reason):
    with pytest.raises(WindowRejected):
        ask_claude(FakeClient([_reply({}, stop_reason=reason)]), "x")


def test_review_maps_verdicts_and_new_cuts():
    words = make_words("una delle delle aziende. " + "parola " * 20 + "È molto molto bello.")
    dubious = [Candidate(25, 25, "repetition", False, "parola ripetuta")]
    client = FakeClient([_reply({
        "verdicts": [{"candidate": 1, "cut": True, "sure": True}],
        "cuts": [{"from_id": 1, "to_id": 1, "kind": "repetition", "sure": True, "reason": "inciampo"}]})])
    result = review_with_claude(words, dubious, client)
    assert result.verdicts == {1: (True, True)}
    assert result.cuts == [Candidate(1, 1, "repetition", True, "inciampo", source="claude")]
    assert result.failed_windows == 0
    assert "C1: parole 25–25" in client.beta.messages.calls[0]["messages"][0]["content"]


def test_review_survives_api_errors():
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    client = FakeClient([anthropic.APIConnectionError(request=request)])
    result = review_with_claude(make_words("ciao a tutti"), [], client)
    assert result.failed_windows == 1
    assert result.cuts == []
    assert "senza Claude" in result.warnings[0]


def test_review_survives_malformed_response():
    client = FakeClient([_reply({"verdicts": [], "cuts": [{"from_id": 1}]})])
    result = review_with_claude(make_words("ciao a tutti"), [], client)
    assert result.failed_windows == 1


class BlockClient:
    """Risponde a ogni blocco con la sua risposta, qualunque sia l'ordine delle chiamate parallele."""

    def __init__(self, replies_by_block):
        self.replies = replies_by_block
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        text = kwargs["messages"][0]["content"]
        block = int(text.split("Blocco ", 1)[1].split("/", 1)[0])
        return _reply(self.replies[block])


def _cut(word, reason):
    return {"from_id": word, "to_id": word, "kind": "repetition", "sure": True, "reason": reason}


def test_review_lets_one_block_decide_each_shared_word():
    # 1700 frasi di una parola: blocchi 0–1499 e 1350–1699, zona condivisa 1350–1499.
    # «artificiale artificiale» (1400–1401) sta nella prima metà della zona, 1470 nella seconda.
    tokens = [f"p{i}." for i in range(1700)]
    tokens[1400], tokens[1401] = "artificiale", "artificiale."
    words = make_words(" ".join(tokens))
    client = BlockClient({
        1: {"verdicts": [], "cuts": [_cut(1401, "blocco 1"), _cut(1470, "blocco 1")]},
        2: {"verdicts": [], "cuts": [_cut(1400, "blocco 2"), _cut(1470, "blocco 2")]}})
    result = review_with_claude(words, [], client)
    assert result.cuts == [Candidate(1401, 1401, "repetition", True, "blocco 1", source="claude"),
                           Candidate(1470, 1470, "repetition", True, "blocco 2", source="claude")]


def test_review_warns_about_candidates_outside_every_block():
    words = make_words(" ".join(f"p{i}." for i in range(1700)))
    dubious = [Candidate(1300, 1600, "retake", False, "")]
    client = FakeClient([_reply({"verdicts": [], "cuts": []}), _reply({"verdicts": [], "cuts": []})])
    result = review_with_claude(words, dubious, client)
    assert result.verdicts == {}
    assert any("nessun verdetto" in w for w in result.warnings)
