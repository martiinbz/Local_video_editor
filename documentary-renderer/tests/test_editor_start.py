from __future__ import annotations

import editor.start as start


def test_main_does_not_start_second_server_when_port_is_busy(monkeypatch, capsys) -> None:
    monkeypatch.setattr(start, "port_is_in_use", lambda host, port: True)
    run = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("uvicorn should not start"))
    monkeypatch.setattr(start.uvicorn, "run", run)
    monkeypatch.setattr(start.webbrowser, "open", lambda url: True)

    start.main()

    assert "ya está activo" in capsys.readouterr().out
