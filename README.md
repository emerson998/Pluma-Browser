# Pluma Browser

**Menos distração. Mais espaço para navegar.**

Navegador desktop experimental para Windows e Linux, com motor **Chromium via Qt WebEngine**, interface nativa minimalista, bloqueio de anúncios por domínio e assistente de IA opcional.

> Versão 0.1.0: primeira base funcional. Não é uma distribuição do Google Chrome nem um fork completo do Chromium. Não há benchmark demonstrando menor RAM que Chrome. O motor Chromium continua sendo a maior parte do consumo e do tamanho do pacote.

## O que está implementado

- Interface escura com acentos verdes, barra de endereço/pesquisa e abas.
- Nova aba nativa: não cria um renderer web até você navegar.
- Congelamento após 60 segundos e descarte após 5 minutos em segundo plano, **somente quando o Chromium recomenda**. Áudio e abas marcadas “Manter ativa” são preservados.
- Perfil compartilhado pelas abas, cache limitado a 64 MiB; sem feed, extensões ou modelo de IA local embutido.
- Bloqueador nativo com lista inicial de 21 domínios de anúncios/rastreamento; inclui subdomínios e exceção por site.
- Janela privada com perfil off-the-record independente.
- Favoritos locais, downloads com escolha do destino, atalhos de teclado.
- Painel IA criado sob demanda: API compatível com OpenAI, Anthropic ou servidor local compatível.
- Endpoint e modelo editáveis. Presets são sugestões, sujeitos à disponibilidade na conta.
- Chave somente em memória por padrão; armazenamento opcional pelo keyring do sistema.
- Texto da página enviado somente com confirmação para cada pergunta, limitado a 24.000 caracteres.
- Respostas exibidas como texto, sem executar HTML ou instruções da IA.

## Executar a partir do código

Requer Python 3.11+ (recomendado 3.12), Windows x64 ou Linux x64 com ambiente gráfico.

### Windows (PowerShell)

    py -3.12 -m venv .venv
    .venv\Scripts\python -m pip install -e .
    .venv\Scripts\python -m pluma

### Ubuntu 24.04 / Linux

    sudo apt-get update
    sudo apt-get install libnss3 libxtst6 libxkbfile1 libasound2t64 libxcb-cursor0 libxcb-icccm4 libxcb-keysyms1 libxcb-shape0 libxcb-xinerama0
    python3 -m venv .venv
    .venv/bin/python -m pip install -e .
    .venv/bin/python -m pluma

Execute como usuário comum. Não desligue a sandbox do Chromium. Outras distribuições precisam dos pacotes equivalentes; o wheel Qt exige glibc compatível.

## Usar IA

1. Clique **IA** e escolha o provedor.
2. Cole sua chave e ajuste o modelo se necessário.
3. Envie uma pergunta. Não é preciso contratar ou hospedar um backend do Pluma.
4. Para analisar a página, marque “Incluir texto da página” e confirme o envio.

As cobranças são do provedor da API. Assinatura de chat não implica crédito de API.
Cada pergunta é independente: o histórico visual não é reenviado ao modelo.
O Pluma não faz chamadas de IA em segundo plano nem salva a conversa.
Servidores locais precisam estar instalados separadamente; o Pluma não baixa modelos.

**Segurança:** APIs remotas exigem HTTPS; HTTP só é aceito em loopback. Redirecionamentos de API não são seguidos. Alterar o endpoint limpa a chave da interface. No Linux, salvar chaves requer um serviço Secret Service/KWallet funcional; sem ele, use modo em memória. A chave não entra no perfil web, no JavaScript de sites ou no QSettings.

## Atalhos

| Atalho | Ação |
|---|---|
| Ctrl+L | Endereço |
| Ctrl+T / Ctrl+W | Abrir / fechar aba |
| Ctrl+R | Recarregar |
| Alt+← / Alt+→ | Voltar / avançar |
| Ctrl+J | Painel de IA |
| Ctrl+Shift+N | Janela privada |

## Pacotes para Windows e Linux

O workflow **Test and build** testa e gera uma pasta portátil para cada sistema.
Após executar no GitHub Actions, baixe o artefato do seu sistema, extraia a pasta inteira e abra Pluma.exe (Windows) ou Pluma (Linux).

Para gerar localmente, no próprio sistema de destino:

    python -m pip install -e ".[dev]"
    python scripts/build.py

Saída: **dist/Pluma/**. Mantenha todos os arquivos juntos. São builds portáteis sem assinatura digital; não há instalador ou atualizador automático nesta versão. Windows deve ser compilado no Windows; Linux no Linux.

## Testes

    python -m pip install -e ".[dev]"
    python -m pytest -q
    python scripts/smoke.py

No Linux sem monitor, use **xvfb-run -a python scripts/smoke.py**.
Os testes unitários usam respostas de API simuladas; não consomem créditos.
O smoke valida interface, abas, perfil privado e renderização do Chromium.

## Medir leveza de verdade

    python scripts/benchmark.py PID --seconds 60

O script soma RSS do processo principal e filhos. RSS pode contar memória compartilhada mais de uma vez: use a mesma métrica para os dois navegadores.

Compare em uma máquina: mesma versão de SO, sites, quantidade de abas, extensões desligadas, cache equivalente e 3 repetições. Meça início, 1/5/20 abas, 5 minutos em repouso e reativação. Registre RAM, CPU, latência de abertura e tamanho instalado. Não compare números de CI com os do seu computador.

## Limitações conhecidas

- Bloqueio apenas por domínio. Não implementa EasyList, filtros cosméticos, scriptlets, atualização de listas ou bloqueio garantido de anúncios em vídeo.
- Suspender/descarregar abas depende do estado recomendado pelo Chromium. Use “Manter ativa” em editores, chamadas e formulários importantes.
- Não inclui sincronização, extensões Chrome, gerenciador de senhas, restauração de sessão, tradução ou integração como navegador padrão.
- Compatibilidade com DRM, codecs proprietários, passkeys e logins que rejeitam webviews precisa de testes específicos.
- Navegação privada não significa anonimato; downloads e envios voluntários à IA deixam rastros fora do perfil.
- Atualizações de segurança do Chromium dependem de atualizar Qt WebEngine e redistribuir o aplicativo. Não há promessa de equivalência à segurança/atualização do Chrome.
- Sem teste real com chaves pagas e sem medição comparativa publicada nesta versão.

## Arquitetura

**pluma/core.py**: políticas testáveis de URL, bloqueio e ciclo de vida.
**pluma/app.py**: shell Qt, abas, perfis, permissões, downloads e painel IA.
**pluma/ai.py**: HTTP limitado, sem acesso a cookies e sem ponte JavaScript.
**scripts/**: build, smoke e medição de memória.

Referências: [ciclo de vida do Qt WebEngine](https://doc.qt.io/qtforpython-6.10/PySide6/QtWebEngineCore/QWebEnginePage.html), [perfil web](https://doc.qt.io/qtforpython-6/PySide6/QtWebEngineCore/QWebEngineProfile.html), [licenças](THIRD_PARTY.md).

## Próximos passos

1. Ampliar bloqueio com motor de filtros e atualização verificável de listas.
2. Medir consumo em hardware real e estabelecer orçamento de RAM/CPU.
3. Validar navegação e acessibilidade em Windows e distribuições Linux.
4. Assinar binários e implementar atualizações de segurança.
5. Evoluir histórico, restauração opcional e importação de favoritos.

MIT para o código do Pluma; dependências mantêm suas licenças.
