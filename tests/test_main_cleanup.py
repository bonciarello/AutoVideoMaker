import main


def test_cleanup_failure_does_not_stop_the_video(monkeypatch, capsys):
    def boom(*args, **kwargs):
        raise RuntimeError("guasto")

    monkeypatch.setattr(main, "run_cleanup", boom)
    assert main.cleanup_or_none([{"id": 0}], "rules", "rifaccio", None, 1.0, 0.05) is None
    assert "pulizia take non riuscita" in capsys.readouterr().out


def test_cleanup_or_none_returns_the_result(monkeypatch):
    monkeypatch.setattr(main, "run_cleanup", lambda *args, **kwargs: "risultato")
    assert main.cleanup_or_none([{"id": 0}], "rules", "rifaccio", None, 1.0, 0.05) == "risultato"
