"""One-off: cria MANIFEST + legenda para a peca social-11748-real (so Instagram)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
PASTA = ROOT / 'producao' / '2026-S21' / 'social-11748-real'
SRC_LEGENDA = ROOT / 'producao' / '_publicado' / 'social-11748-20260519T233557' / 'legenda.txt'

# 1. legenda corrigida (typo da hashtag)
legenda = SRC_LEGENDA.read_text(encoding='utf-8').replace(
    '#NovielloadAdvocacia', '#NovielloAdvocacia'
)
(PASTA / 'legenda.txt').write_text(legenda, encoding='utf-8')
print(f'legenda.txt: {len(legenda)} chars')

# 2. MANIFEST.json: SO instagram
slides = [str(PASTA / f'slide{i:02d}.jpg') for i in range(1, 11)]
manifest = {
    'peca_id': 'social-11748-real',
    'tipo': 'carrossel',
    'pilar': 'Sucessorio',
    'titulo_curto': 'Holding Familiar — para todas as familias',
    'data_publicacao_alvo': '2026-05-20T00:00:00-03:00',
    'status': 'pronta_para_aprovacao',
    'validacoes': {'oab_205': 'aprovado', 'marca': 'v2-conforme', 'ortografia': 'ok'},
    'ativos': {
        'instagram': {
            'imagens': slides,
            'legenda': str(PASTA / 'legenda.txt'),
            'hashtags': [
                '#HoldingFamiliar', '#PlanejamentoSucessório', '#PlanejamentoSênior',
                '#Inventário', '#ITCMD', '#ReformaTributária', '#ProtecaoPatrimonial',
                '#SociedadeAnonima', '#DireitoSucessório', '#NovielloAdvocacia',
                '#AdvocaciaHumanizada', '#MelhorIdade', '#PatrimônioFamiliar',
                '#PlanejamentoTributário', '#Herança',
            ],
            'tipo_post': 'carrossel',
        },
    },
    'cross_link': {'ig_para_wp': False, 'li_para_wp': False, 'linktree_topo': False},
}
(PASTA / 'MANIFEST.json').write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8'
)
print(f'MANIFEST.json escrito: peca_id={manifest["peca_id"]} canais={list(manifest["ativos"].keys())}')

# 3. mostra estado atual do .env
env_path = ROOT / '.env'
for l in env_path.read_text(encoding='utf-8').splitlines():
    if l.startswith('DRY_RUN') or l.startswith('ENABLED_CHANNELS'):
        print(f'.env atual: {l}')
