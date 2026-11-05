# Pluma Browser 0.3

**Menos distração. Mais espaço para navegar.**

Navegador desktop para Windows x64 e Linux x64, com Chromium via Qt WebEngine, interface nativa e IA opcional por chave de API.

## Instalar

Baixe a versão do seu sistema em **[Releases](https://github.com/emerson998/Pluma-Browser/releases)**.

| Sistema | Pacotes |
|---|---|
| Windows | Instalador por usuário e ZIP portátil |
| Ubuntu 24.04 / compatíveis | Pacote .deb e arquivo portátil .tar.gz |

Extraia a pasta portátil inteira antes de executar. Não rode o navegador como root.
Os pacotes Windows ainda não têm assinatura Authenticode: isso exige certificado do publicador.
As releases produzidas pelo workflow incluem SHA256 e atestação de procedência do GitHub.
Para verificar: **gh attestation verify ARQUIVO --repo emerson998/Pluma-Browser**.
No Linux portátil, preserve a permissão de execução: **chmod +x Pluma/Pluma**.

O instalador registra o aplicativo como opção de navegador. Escolha Pluma nas configurações de aplicativos padrão do Windows. No Linux instalado: **xdg-settings set default-web-browser pluma.desktop**. URLs passadas pela linha de comando são abertas no navegador e reutilizam a instância do mesmo usuário.

## O que mudou

| Área | Recursos |
|---|---|
| Economia | Equilibrado/Econômico; suspensão ajustável; abas fixadas e com áudio preservadas; painéis sob demanda |
| Sessão | Gravação atômica; recuperação após reiniciar/falhar; restauração sem carregar todas as abas; reabrir abas fechadas |
| Bloqueio | Motor Rust, regras ABP/uBO suportadas pelo motor, EasyList/EasyPrivacy, filtros CSS, exceções por domínio |
| Navegação | Pesquisa configurável, zoom, buscar texto, silenciar/fixar/duplicar abas, impressão e PDF, tela cheia |
| Favoritos | Edição, pastas, busca, importação HTML/JSON, exportação JSON e migração da versão anterior |
| Downloads | Progresso, pausar/retomar quando o servidor permite, cancelar e escolha do destino |
| Privacidade | Perfis privados, revogar permissões, limpeza de cookies e armazenamento da página, histórico local opcional |
| IA | Streaming, Parar, prazo total, conversa limitada, resumir, explicar/traduzir seleção e prévia editável antes do envio |
| Diagnóstico | Painel RAM/USS/CPU/processos, estados das abas, versão do Chromium e nível das correções |
| Distribuição | Instaladores, pacotes portáteis, checksums, teste do executável e publicação versionada automatizada |

## Proteção específica do YouTube

A partir da 0.3, **Proteção reforçada do YouTube** fica ativa por padrão no menu.
Além das listas de rede, um código pequeno, incluído no próprio aplicativo:

- Remove campos conhecidos de anúncios de respostas do player, preservando os dados do vídeo.
- Oculta alguns formatos promocionais e banners conhecidos.
- Aciona o botão de pular anúncio quando ele está visível e disponível.
- Usa eventos/observação limitada do player; não mantém uma varredura periódica da página inteira.

As exceções por site do botão Proteção também desativam esse tratamento após recarregar.
Se houver falha de reprodução, desmarque a opção no menu e recarregue a página.
Não baixamos código executável de filtros. Os scripts rodam apenas em hosts explícitos
do YouTube e YouTube NoCookie; não acessam chaves da IA, cookies ou APIs do navegador.

**Não há garantia de bloquear todos os anúncios do YouTube.** Formatos entregues junto
ao vídeo, alterações do player e testes da plataforma podem escapar. Os testes usam
payloads e uma página local controlada; não demonstram bloqueio completo no YouTube real.

## Vídeo flutuante

1. Abra um vídeo, por exemplo no YouTube, e inicie a reprodução.
2. Clique **Vídeo** na barra ou use **Ctrl+Shift+V**.
3. Arraste a janela pelo título e ajuste o tamanho pelas bordas/cantos.
4. **Fixar** mantém o quadro por cima de outros aplicativos. Desmarque para uma janela normal.
5. Os controles permitem pausar/reproduzir, silenciar e voltar/avançar 10 segundos. Os controles nativos do vídeo também ficam habilitados.
6. **Voltar à aba**, **Esc** ou fechar o quadro devolvem a mesma página à aba original.

A aba de origem mostra um botão para trazer o vídeo de volta. É possível navegar em outras abas ou minimizar o navegador enquanto o quadro continua aberto. Fechar a aba de origem ou o navegador fecha também o quadro.

O recurso reaproveita o mesmo QWebEngineView e a mesma página: não abre outro stream, não troca para uma URL embed e não cria outro renderer. O vídeo flutuante fica protegido da suspensão automática, mesmo sem áudio. As mudanças visuais são reversíveis e não usam observador DOM ou temporizador permanente.

Compatível com elementos HTML5 video visíveis no documento principal. Players em iframe de outra origem, DRM, codecs indisponíveis ou restrições do site podem impedir o modo. A opção “sempre por cima” também depende do gerenciador de janelas/compositor no Linux. O teste de reprodução usa um vídeo VP8 local; não automatiza acesso a contas do YouTube.

## Leveza

- A nova aba é um widget nativo e não cria uma página Chromium até você navegar.
- A sessão restaurada mantém abas de fundo sem renderer até serem selecionadas.
- Equilibrado: suspender após 60 s e descartar após 300 s, configuráveis.
- Econômico: tempos de até 30 s / 120 s, sempre respeitando o estado recomendado pelo Chromium.
- Abas com áudio recente, fixadas ou marcadas “Manter ativa” ficam ativas.
- O motor de filtros é compartilhado entre perfis; o contador de bloqueios é atualizado em lote.
- Filtros visuais fazem uma varredura limitada após carregar a página, sem observador DOM permanente.
- A biblioteca HTTP de IA e o painel são carregados quando você abre o assistente.
- Não há modelo de IA embutido, feed ou telemetria. O histórico é opcional e limitado a 1.000 páginas.
- Os dados da sessão são salvos com debounce. RAM/CPU são consultadas apenas com o painel de desempenho aberto.
- Cache limitado a 64 MiB **não é limite de RAM**. Chromium e Qt continuam determinando grande parte do consumo e do tamanho instalado.

Ainda não há comparação publicada que comprove consumo menor que Chrome. Medir apenas em CI não representa o seu desktop.

## Bloqueador nativo

As releases já incluem EasyList e EasyPrivacy. Menu → Atualizar listas de bloqueio busca novas versões por HTTPS, valida formato/tamanho e registra origem, SHA256 e data no cache. Uma resposta inválida mantém as listas anteriores. A atualização semanal é opcional em Preferências; não há download automático a cada abertura.

Ao executar diretamente do código, use essa ação para carregar as listas completas; até lá, uma lista inicial de domínios já bloqueia algumas redes conhecidas.

O motor implementa filtros de rede e seletores CSS suportados pela versão da biblioteca. Não executamos scriptlets de listas remotas. Não há promessa de bloquear todos os anúncios em vídeo nem de compatibilidade total com todos os filtros do uBlock Origin. Sites podem precisar de uma exceção. As licenças das listas permanecem dos autores; veja [THIRD_PARTY.md](THIRD_PARTY.md).

## IA

1. Abra **IA**, escolha o provedor e cole sua chave.
2. Modelo e endpoint podem ser alterados; configurações não secretas são lembradas em janelas normais.
3. Salvar a chave no cofre do sistema é opcional; o padrão é mantê-la somente em memória.
4. Para resumir uma página ou explicar/traduzir seleção, revise o texto e confirme o destino antes de enviar.
5. O botão Parar cancela cooperativamente a consulta; um servidor parado pode levar até o timeout de leitura para liberar a conexão.

Compatível com Chat Completions de APIs OpenAI compatíveis, Messages da Anthropic e servidores locais compatíveis. Presets podem ser ajustados conforme os modelos disponíveis na conta. Provedores precisam suportar streaming nesses endpoints.

- Contexto de página: até 24.000 caracteres.
- Pergunta: até 12.000 caracteres.
- Histórico enviado: até 12 mensagens e orçamento de aproximadamente 48.000 caracteres (não é uma contagem exata de tokens).
- Saída solicitada: até 2.048 tokens; resposta de rede limitada a 2 MB.
- Prazo total verificado durante a leitura: 60 s; conexão/leitura têm timeout de 8 s.
- APIs remotas exigem HTTPS, sem redirecionar credenciais. HTTP é aceito somente em loopback.
- A IA não executa ações no navegador. Respostas são texto. Cookies e a chave não são expostos a sites.
- Assinaturas de chat não incluem necessariamente créditos de API. Os custos são do seu provedor.

## Privacidade

Cada janela privada usa perfil em memória, destruído ao fechar. Sessões, histórico e favoritos não são gravados por ela. Downloads e envios voluntários à IA acontecem fora da proteção do perfil privado. Salvar uma chave no cofre, se escolhido explicitamente, persiste a chave.

Menu → Privacidade deste site permite revogar permissões e solicitar limpeza de cookies, local/session storage, IndexedDB e Cache Storage da página atual. Páginas abertas podem recriar esses dados; operações IndexedDB podem ser bloqueadas por conexões abertas. Há também limpeza global de cookies e cache HTTP do perfil. Isso não representa apagamento completo de todo o armazenamento de todas as origens.

Não há sincronização ou gerenciador de senhas embutido. Não enfraqueça sandbox, TLS ou isolamento do Chromium para economizar recursos.

## Atualizações

Menu → Verificar atualizações consulta a última release oficial e oferece abrir a página de download. A instalação continua sendo uma ação do usuário: o aplicativo não baixa nem executa atualizadores em segundo plano.

O workflow testa código e executável, gera instaladores e pacotes, calcula checksums e publica a versão ainda não existente em Releases. Mudanças posteriores exigem aumentar a versão. A publicação usa permissões temporárias do GitHub Actions e atestação de procedência; não exige colocar tokens pessoais no código.

Dependabot propõe atualizações do motor e das dependências. A tela Sobre mostra a versão Chromium e o nível das correções incluídas. Atualizações do motor precisam passar por testes e redistribuição; não existe garantia de paridade de atualização com Chrome.

## Executar pelo código

Recomendado Python 3.12.

Windows PowerShell:

    py -3.12 -m venv .venv
    .venv\Scripts\python -m pip install -e .
    .venv\Scripts\python -m pluma

Ubuntu 24.04:

    sudo apt-get update
    sudo apt-get install python3-venv libegl1 libopengl0 libgl1 libxkbcommon-x11-0 libnss3 libxtst6 libxkbfile1 libasound2t64 libxcb-cursor0 libxcb-icccm4 libxcb-keysyms1 libxcb-shape0 libxcb-xinerama0
    python3 -m venv .venv
    .venv/bin/python -m pip install -e .
    .venv/bin/python -m pluma

Outras distribuições precisam dos pacotes equivalentes e glibc compatível com os wheels Qt. Wayland, codecs proprietários, DRM, passkeys e sites que restringem webviews precisam de validação específica. Não são cobertos pela promessa de suporte a Ubuntu/Windows.

## Atalhos

| Atalho | Ação |
|---|---|
| Ctrl+L | Endereço |
| Ctrl+T / Ctrl+W | Abrir / fechar aba |
| Ctrl+Shift+T | Reabrir aba |
| Ctrl+F / Ctrl+G | Buscar / próxima ocorrência |
| Ctrl++ / Ctrl+- / Ctrl+0 | Zoom |
| Ctrl+M | Silenciar |\n| Ctrl+Shift+V | Vídeo flutuante |
| Ctrl+P | Imprimir |
| Ctrl+J | IA |
| Ctrl+Shift+J | Downloads |
| Ctrl+H | Histórico |
| Ctrl+Shift+N | Janela privada |
| Alt+← / Alt+→ | Voltar / avançar |
| Esc | Sair de tela cheia |

## Validação e build

    python -m pip install -e ".[dev]"
    python -m pytest -q
    python scripts/smoke.py
    python scripts/features_smoke.py\n    python scripts/video_smoke.py
    python scripts/youtube_smoke.py
    python scripts/build.py
    python scripts/packaged_smoke.py
    python scripts/package.py

Linux sem monitor: execute os smokes com **xvfb-run -a**. Build exige internet para obter as listas completas. O empacotamento Windows exige Inno Setup 6; Linux exige dpkg-deb. Compile no sistema de destino. A pasta portátil é **dist/Pluma**; os pacotes ficam em **release**.

Os testes usam respostas de IA simuladas e páginas locais; não consomem créditos. O teste empacotado abre o executável final e verifica renderização Chromium e perfil privado.

## Benchmark reproduzível

    python scripts/benchmark.py PID --seconds 60 --label pluma --output pluma.json

O script mede toda a árvore de processos e registra RSS, USS, CPU, pico e amostras. Repita para Chrome na mesma máquina, com mesmos sites/cache e sem extensões, em cenários de 1, 5 e 20 abas, antes/depois de repouso. Faça ao menos três repetições. RSS pode contar páginas compartilhadas duas vezes; CPU pode passar de 100% em vários núcleos.

Também registre abertura até primeira página utilizável, tamanho instalado e latência ao reativar abas. Não reduza isolamento ou segurança para melhorar números.

## Código

app.py: shell e navegação. features.py: sessões e comandos. dialogs.py: painéis nativos.
blocking.py: motor Rust e listas. ai_panel.py / ai.py: assistente e API.
storage.py: persistência limitada. instance.py: reutilização de instância.
updates.py: consulta de releases. scripts/: builds, testes e medição.

Código do Pluma: MIT. Dependências e listas mantêm suas licenças.
