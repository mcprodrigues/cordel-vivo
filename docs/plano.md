# Cordel Vivo: arquitetura e roadmap

Nov 24, 2026 · @Clara

## Visão

O Cordel Vivo transforma folhetos de cordel digitalizados num acervo pesquisável por tema, por forma poética e pela capa. A visão computacional lê o folheto, o código reconhece a métrica e a rima, e o LLM só enriquece o que o código já leu.

**Para quem:** estudantes e professores de literatura, pesquisadores de cultura popular e cordelistas que querem estudar a tradição.

**Exemplos de consulta:**

- "décimas sobre Lampião escritas antes de 1940";
- "folhetos sobre a seca e a migração para o Sul";
- "capas parecidas com esta xilogravura";
- "por que esta estrofe não é uma sextilha perfeita?".

**O que ele prova no portfólio:**

- visão computacional em documentos difíceis (papel amarelado, impressão irregular, ortografia antiga);
- regras determinísticas onde elas bastam, e LLM validado onde não bastam;
- ingestão assíncrona, busca híbrida multimodal e um grafo de conhecimento;
- avaliação com números publicados no README, camada por camada.

**Diferencial de pesquisa:** a autoria no cordel é um problema real. João Martins de Athayde comprou os direitos da obra de Leandro Gomes de Barros e assinou o próprio nome em centenas de folhetos que eram de Leandro ([SciELO](https://www.scielo.br/j/rieb/a/SZGpzJpRJfQp8jPtcgpcjFw/)). Uma fase opcional pode explorar estilometria para levantar hipóteses de autoria, sempre como hipótese e nunca como veredito.

## Acervo e direitos

O corpus da v1 deve ter só folhetos em domínio público, com a licença e a origem de cada item gravadas junto com o dado. Pela Lei 9.610/98 (art. 41), os direitos patrimoniais duram 70 anos a partir de 1º de janeiro do ano seguinte à morte do autor. Em 2026, isso cobre autores mortos até 1955, como Leandro Gomes de Barros (morto em 1918).

| Fonte | O que tem | Como usar no projeto |
| --- | --- | --- |
| [Fundação Casa de Rui Barbosa](https://catracalivre.com.br/educacao/acervo-de-cordel/) | Mais de 9.000 folhetos, 2.340 digitalizados, com busca por palavra-chave e autor | Fonte principal do piloto. Confirmar os termos de reprodução das imagens antes de baixar em lote. |
| [Biblioteca Virtual Cordel, Univ. de Poitiers](https://www.scielo.br/j/rieb/a/SZGpzJpRJfQp8jPtcgpcjFw/) | Acervo Raymond Cantel | O próprio projeto propôs acesso livre para o domínio público e restrito para o resto: mesma regra que você vai seguir. |
| [Portal do Cordel, IEB-USP](https://sites.usp.br/portaldocordel/) | Coleções por doador, incluindo gravuras | Fonte complementar, sobretudo para xilogravuras. |
| [Cordelteca da UECE](https://www.uece.br/eduece/wp-content/uploads/sites/88/2025/12/Cordelteca-da-Biblioteca-Central-da-Universidade-Estadual-do-Ceará-EdUECE.pdf) | Acervo da Biblioteca Central | O elo cearense. Bom candidato a parceria. |
| Folhetos digitalizados por você | Folhetos comprados em Fortaleza | Só com autorização por escrito do cordelista. É o caminho para incluir obras contemporâneas. |

**Regras do acervo:**

- A xilogravura da capa tem autor próprio, o gravurista, e direitos próprios: o prazo de domínio público é calculado por peça, não por folheto.
- A autoria impressa nem sempre é a real (caso Athayde e Leandro): guarde a autoria *declarada* e a *atribuída*, com a fonte de cada uma.
- Item sem licença confirmada entra no índice só com metadados e link para a fonte, nunca com a imagem.

## Arquitetura

Cada folheto passa por quatro etapas assíncronas, cada uma um job idempotente na fila, e só o que passou pelas validações chega ao índice. Cada serviço tem o seu Dockerfile e o seu `.env.example`, e eles conversam só por HTTP ou pela fila.

&#91;embedded content: arquitetura · API, fila, 4 workers, busca e armazenamento\]

A etapa Poética está em destaque porque é o diferencial: ela não usa LLM. Se o modelo de embedding mudar, só a Indexação é reprocessada.

## Pipeline de visão computacional e OCR

O serviço de leitura entrega, para cada página, linhas de texto com bounding box e confiança, separadas em estrofes. Todo o pré-processamento é OpenCV determinístico. O LLM só entra para desempatar trechos difíceis.

1. **Normalização:** PDF ou imagem → render com PDFium a 300 DPI, com checagem do DPI mínimo (a pendência que você já conhece da Exitus).
2. **Classificação da página:** capa ou miolo. Comece com uma heurística (área de tinta contínua grande = xilogravura) e só treine um classificador pequeno se ela falhar no golden set.
3. **Capa:** recorte da xilogravura pela maior região de tinta (morfologia + contornos), mais o OCR do título e do autor.
4. **Miolo:**
   1. *deskew* por perfil de projeção ou Hough;
   2. remoção do amarelado e das sombras (estimativa do fundo por dilatação e divisão);
   3. binarização adaptativa (Sauvola), que lida melhor com papel irregular do que Otsu;
   4. segmentação em linhas por perfil horizontal, e em estrofes pelos espaços verticais maiores.
5. **OCR por consenso:** dois motores leem cada linha, por exemplo Tesseract (`por`) e um modelo de visão-linguagem. Se as leituras forem iguais, aceita. Se divergirem, um adjudicador recebe o recorte da linha e as duas leituras. É o seu padrão da `avaliacao_ia`, reescrito do zero num domínio novo.
6. **Transcrição em duas camadas:** a *diplomática*, fiel à grafia do folheto ("pharmacia", "ella"), e a *normalizada*, usada na busca. A normalização é feita por tabela de regras, não por LLM.

O motor de OCR final é decidido por benchmark na Fase 1 (CER no golden set), não por preferência.

## Análise poética determinística

A forma de cada estrofe é reconhecida por código puro, testado sem LLM. Este é o coração técnico e o que diferencia o projeto de um "RAG sobre PDFs".

**Escansão:** conta as sílabas poéticas até a última tônica, com regras de acentuação do português e de sinalefa e elisão. Como a sinalefa é opcional, o módulo devolve *todas* as leituras possíveis de um verso, e a forma escolhida é a que melhor encaixa na estrofe.

**Rima:** compara os versos da vogal tônica até o fim, após normalização fonética (s / ss / ç, grafias antigas), e separa rima consoante de toante.

**Formas da v1** (esquemas a confirmar com a bibliografia antes de virarem teste):

| Forma | Versos | Sílabas | Esquema de rima |
| --- | --- | --- | --- |
| Quadra | 4 | 7 | XAXA |
| Sextilha | 6 | 7 | XAXAXA |
| Setilha | 7 | 7 | XAXABBA |
| Décima | 10 | 7 | ABBAACCDDC |
| Martelo agalopado | 10 | 10 | ABBAACCDDC |
| Galope à beira-mar | 10 | 11 | ABBAACCDDC, com o mote "beira do mar" |

**Saída:** a forma detectada, a confiança e os desvios, por exemplo "verso 3 com 8 sílabas" ou "verso 6 não rima com o 4". É isso que responde a "por que esta estrofe não é uma sextilha perfeita?".

**Truque que vale destacar no README:** a métrica também serve para checar o OCR. Uma estrofe perfeita exceto por uma palavra provavelmente tem um erro de leitura nessa palavra. Ela é sinalizada (`SUSPEITA_OCR`) e volta para o adjudicador com o contexto da forma esperada.

## Enriquecimento com LLM e grafo

O LLM extrai o que as regras não conseguem (temas, personagens, lugares, gênero), e toda extração precisa citar os versos de onde saiu. O código confere a citação antes de gravar.

**Extração (o LLM decide, o código executa):**

- Saída em Pydantic com vocabulário controlado: temas de uma lista fechada (seca, cangaço, religiosidade, peleja, romance, gracejo, política, acontecido…) e gênero (peleja, romance, ABC, exemplo, notícia).
- Cada personagem, lugar ou tema aponta para ids de linhas. O código verifica que o trecho existe na transcrição; se não existir, descarta.
- Dois modelos de famílias diferentes extraem às cegas. O que bate entra, o que diverge vai para adjudicação ou fica como `INCERTO`.

**Grafo de conhecimento**, guardado no Postgres (tabelas de nós e arestas, consultas recursivas) antes de pensar em Neo4j:

- nós: folheto, autor declarado, autor atribuído, gravurista, personagem, lugar, tema, forma;
- arestas: *escreveu*, *gravou a capa*, *menciona*, *se passa em*, *é variante de* (a mesma história recontada por autores diferentes).

**Agente de perguntas (LangGraph):** roteador → busca híbrida, consulta ao grafo ou análise de forma → resposta com citação de folheto e verso. Sem evidência, ele se abstém em vez de inventar.

**Fase opcional, estilometria:** frequência de palavras funcionais, preferências de rima e de forma por autor, para levantar hipóteses sobre folhetos de autoria disputada. Sempre exibida como hipótese com o grau de confiança.

## Busca e API

A busca combina texto completo em português, vetores e filtros estruturados, funde os resultados por RRF e reordena com um reranker. Os filtros de forma, tema, autor e década vêm das etapas anteriores, não de adivinhação do LLM.

- **Léxica:** `tsvector` do Postgres com `unaccent` sobre a transcrição normalizada.
- **Densa:** embeddings de estrofe (não de página, porque a estrofe é a unidade de sentido do cordel) e embeddings de imagem das capas (SigLIP ou CLIP) no pgvector.
- **Fusão:** RRF entre léxica e densa, depois um reranker cross-encoder multilíngue nos 50 primeiros.

| Método e rota | O que faz |
| --- | --- |
| `POST /v1/folhetos` | Envia um folheto. Devolve `202` com o id do job; o hash SHA-256 do arquivo serve de chave de idempotência. |
| `GET /v1/jobs/{id}` | Estado do processamento por etapa (leitura, poética, enriquecimento, indexação). |
| `GET /v1/folhetos/{id}` | Metadados, licença, estrofes nas duas transcrições, forma e capa. |
| `GET /v1/folhetos/{id}/estrofes/{n}/analise` | Escansão verso a verso, esquema de rima e desvios. |
| `GET /v1/busca` | Busca híbrida com `q`, `forma`, `tema`, `autor` e `decada`. |
| `POST /v1/busca/capas` | Busca por imagem: capas parecidas com a enviada. |
| `POST /v1/perguntas` | Agente de perguntas, com citações ou abstenção. |
| `GET /health` | Única rota pública. |

O contrato fica versionado em `docs/contrato-api-v1.md` e muda junto com o código, como você já faz no `api_ia`.

## Avaliação

Cada camada tem o seu golden set e as suas métricas, e nenhuma mudança de modelo ou prompt entra sem comparar com a versão anterior. Os tamanhos abaixo são sugestões para caber no trabalho de uma pessoa; as metas ficam em aberto até a primeira linha de base.

| Camada | Golden set sugerido | Métricas |
| --- | --- | --- |
| OCR | 50 páginas transcritas à mão | CER e WER, por motor e com consenso |
| Segmentação | As mesmas 50 páginas | Acerto das fronteiras de estrofe |
| Forma poética | 200 estrofes anotadas | Acurácia da forma, erro médio de sílabas por verso |
| Extração | 100 folhetos anotados | F1 por tema; citações que existem no texto (verificado por código) |
| Busca textual | 60 consultas com os folhetos relevantes | recall@10 e nDCG@10, comparando léxica, densa e híbrida |
| Busca por capa | Pares de capas semelhantes | recall@5 |
| Agente | 40 perguntas, incluindo as sem resposta no acervo | Fidelidade, abstenção e relevância, por um juiz de outra família de modelo |

**Regras do harness:**

- A suíte do CI nunca chama LLM nem rede; o que gasta token fica em `*_live.py`.
- O comando de avaliação tem `--comparar-com` e falha se alguma métrica piorar.
- O juiz é calibrado com anotação humana (kappa de Cohen) antes de os números dele irem para o README. Aqui dá para fechar a pendência que ficou aberta na Exitus, com anotadores de Letras.
- O README publica a tabela de resultados, com data e commit.

## Roadmap por fases

São seis fases, de 13 a 16 semanas de dedicação parcial (estimativa), e cada uma termina num portão mensurável. Ao fim da F3 o projeto já é mostrável; F4 e F5 transformam ele em vitrine.

&#91;embedded content: roadmap · 6 fases e 5 portões\]

O portão da F0 está em destaque porque é o único que pode mudar o escopo do acervo inteiro.

## Riscos e decisões em aberto

O maior risco não é técnico: é o direito de uso das imagens. Resolva isso na Fase 0, antes de escrever o pipeline.

| Risco | Mitigação |
| --- | --- |
| Os termos de reprodução dos acervos não permitirem baixar as imagens em lote | Pedir autorização pelo atendimento digital da FCRB ou indexar só metadados com link. Plano B: folhetos digitalizados por você, com autorização. |
| Xilogravura de gravurista ainda protegido num folheto em domínio público | Licença por peça; a capa fica fora do índice visual até ser confirmada. |
| Autoria declarada diferente da real | Guardar as duas, com fonte, e nunca "corrigir" sem referência. |
| OCR ruim em papel muito degradado | Consenso entre motores, a checagem pela métrica e uma fila de revisão manual. |
| Escansão ambígua | Devolver várias leituras e escolher pela estrofe, não pelo verso isolado. |
| Escopo crescer demais | O grafo e a estilometria só entram depois de a busca ter números publicados. |

**Decisões para tomar (e registrar em ADR):**

- [ ] Postgres + pgvector ou Weaviate? Recomendo Postgres: mostra uma stack diferente da do Astros e junta texto, vetor e grafo num lugar só.
- [ ] Motor de OCR principal, decidido por CER no golden set.
- [ ] Fila: tabela no Postgres com `SKIP LOCKED` ou Redis com RQ.
- [ ] Front: Next.js (que está no seu README) ou outro.
- [ ] Nome do repositório e licença do código (MIT ou Apache-2.0); a licença dos dados é outra.

Nenhum código, prompt ou dado da Exitus entra no projeto: os padrões (consenso, adjudicação, harness) são reescritos do zero.

## Fontes

- [Acervo disponibiliza mais de 9.000 folhetos de cordel](https://catracalivre.com.br/educacao/acervo-de-cordel/), Catraca Livre
- [Literatura de cordel e valorização digital: o direito de propriedade em questão](https://www.scielo.br/j/rieb/a/SZGpzJpRJfQp8jPtcgpcjFw/), Revista do IEB (SciELO)
- [Cultura e literatura popular em verso no acervo digital de cordéis da FCRB](https://periodicos.ufpb.br/index.php/biblio/article/view/65388), Biblionline
- [Portal de Literatura de Cordel](https://sites.usp.br/portaldocordel/), IEB-USP
- [Cordelteca da Biblioteca Central da UECE](https://www.uece.br/eduece/wp-content/uploads/sites/88/2025/12/Cordelteca-da-Biblioteca-Central-da-Universidade-Estadual-do-Ceará-EdUECE.pdf), EdUECE
- [Solicitar acesso e reprodução de acervo da FCRB](https://www.gov.br/pt-br/servicos/solicitar-acesso-e-ou-reproducao-de-acervo-bibliografico-da-fundacao-casa-de-rui-barbosa), gov.br
