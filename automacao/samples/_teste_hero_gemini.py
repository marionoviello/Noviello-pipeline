"""Smoke test: gera 1 hero real via Gemini pra ver qualidade."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

for env_file in (ROOT / ".env", ROOT.parent / ".env"):
    if env_file.exists():
        for linha in env_file.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            k, _, v = linha.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from src.image_gen import GeradorImagens, _ambiente_por_tema, _sujeito_por_categoria  # noqa: E402

api_key = os.environ.get("GOOGLE_AI_API_KEY", "")
if not api_key:
    print("GOOGLE_AI_API_KEY ausente no .env")
    sys.exit(1)

destino = ROOT / "samples"
destino.mkdir(exist_ok=True)

titulo = "Doação com Reserva de Usufruto: Planeje o Futuro da Sua Família"
lead = "Você já parou para pensar em como deseja organizar a sucessão do seu patrimônio? Muitos buscam formas de garantir herança aos herdeiros sem burocracias."
categorias = ["Planejamento Sucessório"]

print(f"Artigo: {titulo}")
print(f"Sujeito: {_sujeito_por_categoria(categorias, titulo)[:120]}...")
print(f"Ambiente: {_ambiente_por_tema(lead, titulo)[:120]}...")
print()
print("Chamando Gemini (6-10s)...")

import time
t0 = time.monotonic()
gen = GeradorImagens(api_key)
path = gen.gerar_hero_artigo(
    titulo=titulo, lead=lead, categorias=categorias,
    pasta_destino=destino, nome_arquivo="teste-hero-sucessorio.png",
)
dur = time.monotonic() - t0

print(f"OK em {dur:.1f}s: {path}")
print(f"Tamanho: {path.stat().st_size:,} bytes")
