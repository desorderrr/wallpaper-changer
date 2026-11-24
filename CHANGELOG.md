# Changelog

Todas as alterações relevantes deste projeto ficam registadas aqui.
O formato segue [Keep a Changelog](https://keepachangelog.com/pt-PT/1.1.0/)
e o projeto usa [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [2.3.0] — 2026-11-24

### Adicionado

- Retries com backoff exponencial nas três fontes de imagens (Unsplash, Bing e Wallhaven): erros transitórios de rede, `429` e `5xx` já não deitam fora o ciclo inteiro da fonte.
- Rotação do ficheiro de log (`log.txt` roda para `log.txt.1` ao passar de 1 MB).
- Job de lint (ruff) no CI e cobertura de testes com `pytest-cov`.
- CI passa a testar **Python 3.10 e 3.12** (antes só 3.12), mantendo os três sistemas operativos.
- Metadados de packaging: homepage/repositório no `pyproject.toml` e classificador de licença MIT.
- Novos testes: dedupe na sugestão, rotação do log, limpeza de ficheiros órfãos e versão única.

### Corrigido

- A **"Nova sugestão"** agora também rejeita wallpapers já usados (antes só verificava o tom), cumprindo a promessa de "sem repetições".
- Ficheiros de imagem são sempre fechados (`with Image.open(...)`) — em Windows os handles abertos podiam impedir a limpeza automática de imagens antigas.
- Um wallpaper que falhe ao ser aplicado já não deixa um ficheiro órfão na pasta de imagens.
- Estado de execução (`last_change`, `last_source`, …) protegido por lock — já não há leituras inconsistentes entre a UI e os workers.
- Escaping do AppleScript no macOS agora também escapa barras invertidas.

### Alterado

- A versão passou a ter **uma única fonte de verdade** (`wallpaper_changer/__init__.py`); o `pyproject.toml` lê-a dinamicamente e o `config.py` importa-a.
- A galeria de imagens recentes é calculada num worker (fora do thread da UI), evitando congelamentos na janela.
- Removido o parâmetro não usado de `_enabled_sources`.

## [2.2.1] — 2026

- Arranque no Windows usa `pythonw.exe` (sem janela de consola).
- Bandeja robustecida: fallback X11 no Linux, diálogo de aviso e mutex de instância única no Windows.

## [2.2.0] — 2026

- Histórico de wallpapers usados (hash exato + percetual) para nunca repetir imagens.

## [2.1.0] — 2026

- Pré-visualização tipo Wally, fonte Wallhaven (sem key), mais intervalos, pausa e correção da deteção de tema.

## [2.0.0] — 2026

- Primeira versão pública com CI nas três plataformas e releases automáticos por tag `v*`.
