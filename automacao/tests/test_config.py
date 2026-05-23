from src.config import Config, _bool, _make_getter, load_config


def test_bool_aceita_variantes_verdadeiras():
    for v in ("1", "true", "TRUE", "yes", "sim", "on", " True "):
        assert _bool(v) is True


def test_bool_rejeita_o_resto():
    for v in ("0", "false", "nao", "", "off", "qualquer"):
        assert _bool(v) is False


def test_getter_prioriza_env_file_nao_vazio(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("CHAVE_A=valor_arquivo\nCHAVE_VAZIA=\n", encoding="utf-8")
    monkeypatch.setenv("CHAVE_A", "valor_windows")
    monkeypatch.setenv("CHAVE_VAZIA", "valor_windows_vazia")
    _get = _make_getter(env)
    # .env nao-vazio vence
    assert _get("CHAVE_A") == "valor_arquivo"
    # .env vazio cede para o ambiente do Windows
    assert _get("CHAVE_VAZIA") == "valor_windows_vazia"
    # ausente em ambos -> default
    assert _get("CHAVE_INEXISTENTE", "padrao") == "padrao"


def test_load_config_retorna_config_com_paths():
    cfg = load_config()
    assert isinstance(cfg, Config)
    assert cfg.automacao_dir.name == "automacao"
    assert cfg.producao_dir.name == "producao"
    assert cfg.state_dir.is_dir()
    assert cfg.logs_dir.is_dir()


def test_load_config_enabled_channels_e_lista():
    cfg = load_config()
    assert isinstance(cfg.enabled_channels, list)
    assert all(c == c.lower() for c in cfg.enabled_channels)


def test_channel_enabled():
    cfg = load_config()
    cfg.enabled_channels = ["instagram", "wordpress"]
    assert cfg.channel_enabled("instagram") is True
    assert cfg.channel_enabled("linkedin") is False


def test_config_anthropic_e_fila_social():
    cfg = load_config()
    assert "api_key" in cfg.anthropic
    assert "model" in cfg.anthropic
    assert cfg.anthropic["model"]  # tem default
    assert cfg.wp_categoria_fila_social  # tem default
    assert cfg.anthropic_pronto() == bool(cfg.anthropic.get("api_key"))
