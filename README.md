# Português por Lógica

Aplicação web para estudar gramática da Língua Portuguesa como **raciocínio estruturado**: morfologia, relações entre as palavras e resolução de questões de concurso. O foco não é decorar a resposta, e sim o processo que leva a ela.

> Princípio central: ensinar o processo de raciocínio necessário para encontrar a resposta, não apenas a resposta.

## Executar localmente

Requisitos: Python 3.12+.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # opcional: configure a chave de IA
streamlit run app.py
```

Testes:

```bash
pytest
```

O banco SQLite é criado automaticamente em `data/estudos.db` na primeira execução (migrações e sincronização de conteúdo rodam na inicialização).

### IA (opcional)

Defina `ANTHROPIC_API_KEY` no `.env` para habilitar a análise livre de textos, a resolução de questões inéditas e a avaliação de justificativas. Sem chave, o app continua funcional com conteúdo e exercícios revisados e **informa** que a análise livre está indisponível. Ele nunca exibe uma análise fictícia.

| Variável | Padrão | Uso |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Habilita a IA |
| `PPL_AI_PROVIDER` | automático | `none` desliga a IA mesmo com chave |
| `PPL_AI_MODEL` | `claude-opus-5-5` | Modelo usado |
| `PPL_AI_EFFORT` | `medium` | Esforço de raciocínio (`low`/`medium`/`high`) |
| `PPL_DATABASE_URL` | `sqlite:///data/estudos.db` | URL do banco |

## Deploy (Railway)

`railway.json` define o comando de start (`streamlit run app.py --server.port $PORT ...`) e o healthcheck `/_stcore/health`. Para que o histórico de estudos sobreviva aos deploys, monte um **volume** em `/data` e defina `PPL_DATABASE_URL=sqlite:////data/estudos.db`.

> O MVP não tem autenticação: quem tiver a URL pública usa o mesmo banco de estudos.

## Arquitetura

```text
app.py                      entrada Streamlit (navegação, acessibilidade)
src/
  core/        models.py    SQLAlchemy: entidades e restrições de integridade
               database.py  engine, migrações versionadas, sessões
               schemas.py   contratos Pydantic (conteúdo, análises, saídas da IA)
  services/    content_service.py   carrega e valida os JSON de data/, espelha no banco
               grammar_service.py   motor sem IA: segmentação, posições, análises revisadas, pistas lexicais
               question_parser.py   interpreta questões coladas (alternativas, comando, assunto)
               question_service.py  seleção, correção, tentativas, simulados
               feedback_service.py  feedback pedagógico a partir do conteúdo revisado
               revision_service.py  revisão espaçada (1→3→7→15→30 dias)
               stats_service.py     estatísticas derivadas das tentativas
               ai_service.py        camada de IA desacoplada (provedor substituível)
  components/  theme.py, word_analyzer.py, question_card.py, progress_chart.py
  pages/       home, aprender, laboratorio, questoes, exercicios, revisoes, dashboard
data/
  areas.json            áreas e assuntos
  lessons/*.json        12 aulas (as 10 classes + locução adjetiva e adverbial)
  questions/*.json      66 questões revisadas
  examples/analises.json  20 frases com análise revisada (inclui os 12 casos obrigatórios)
  tutor/roteiros.json   roteiros do tutor socrático
tests/                  76 testes (pytest)
```

### Modelo de dados

- **Conteúdo** (espelho dos JSON, que são a fonte da verdade): `AreaEstudo` 1—N `Assunto` 1—N `Conteudo` / `Questao`.
- **Estudo**: `Tentativa` (N—1 `Questao`, N—1 `Simulado` opcional), `Revisao` (1—1 `Assunto`), `Simulado`, `AnaliseTexto`.
- Restrições: FKs com `PRAGMA foreign_keys=ON`, `CHECK` de dificuldade e de tempo não negativo, `UNIQUE` de revisão por assunto.
- Migrações: lista versionada em `database.py` (`schema_version`). Novas versões são acrescentadas ao final.

### Decisões arquiteturais

1. **Conteúdo em JSON validado por Pydantic.** Revisar e expandir o conteúdo não exige mexer no código. Um erro de autoria (resposta fora das alternativas, destaque ausente do texto, assunto inexistente) quebra a inicialização e os testes, em vez de chegar ao estudante.
2. **Honestidade antes de cobertura.** Sem IA, só as frases com análise revisada recebem classificação completa. Para as demais, o sistema lista apenas as *classes possíveis* das palavras de classe fechada e diz que a análise contextual depende da IA.
3. **Posições sempre recalculadas sobre o texto original.** Os índices devolvidos pela IA não são aceitos como vêm. Se a IA "corrigir" o texto ou inventar uma palavra, o elemento é descartado com aviso.
4. **IA atrás de um protocolo (`ProvedorLLM`).** Trocar de provedor é implementar `gerar_json()`; o resto do app não muda. A saída usa *structured outputs* com JSON Schema derivado dos modelos Pydantic e é validada de novo no app.
5. **Segurança contra instruções embutidas.** O texto do estudante vai delimitado e declarado como dado. Delimitadores falsos dentro do texto são neutralizados. Alternativas e gabaritos inexistentes são descartados, e a resposta da IA é sempre rotulada como sugestão, nunca como gabarito oficial.
6. **Locuções não são classes.** São `Expressao` sobre elementos que mantêm sua própria classe.
7. **Classe × função.** Cada elemento separa a classe morfológica (`classe`) da função sintática (`funcao_sintatica`), e a interface mostra os dois níveis em abas distintas.
8. **Revisão espaçada por assunto** com proteção contra "farm" (vários acertos no mesmo dia não avançam) e ajuste por desempenho.

## O que está implementado (Versão 1)

- Início com resumo, retomada de estudos e próximas revisões.
- Aprender: três áreas e as classes complementares, com 12 aulas (conceito, subtópicos, regras, exemplos, contraexemplos, exceções, comparação de contextos).
- Gramática em Código: fluxograma (Graphviz), pseudocódigo, Python e limitações de cada aula.
- Laboratório: seis modos, frases revisadas com palavras clicáveis, tabela, diagrama de relações, morfologia × sintaxe, ambiguidades e fixação. Análise livre por IA quando configurada.
- Resolver Questões: etapas 1 a 3 sem IA (assunto por palavras-chave, comando, alternativas). Etapas 4 a 7 revisadas para questões do banco; para questões inéditas, sugeridas por IA quando configurada.
- Aprender Raciocinando: tutor socrático com 5 roteiros revisados, que verifica a justificativa além da resposta e tem o botão "Mostrar resposta".
- Exercícios: os modos Treino, Identificar, Relacionar, Comparar, Encontrar o Erro, Justificar e Simulado, com 10 tipos de questão.
- Feedback com alternativa escolhida, correta, diagnóstico do erro, regra, exemplo diferente e questão semelhante.
- Revisões: revisão espaçada, "Revisar meus erros" (refazer ou variação da mesma regra) e agenda completa.
- Desempenho: métricas e gráficos (por área, semanal, assuntos difíceis, por nível, simulados), com filtros por área, assunto, período e dificuldade.
- Acessibilidade: alto contraste, fonte ajustável, rótulo textual em cada classe, foco visível.

## Limitações conhecidas

- Sem IA, o Laboratório classifica completamente apenas as 20 frases revisadas.
- Justificativas abertas sem IA usam autoavaliação, com apoio de palavras-chave de referência.
- A "variação" de uma questão é outra questão revisada da mesma regra; variações geradas automaticamente ficam para versões futuras.
- O tutor socrático dinâmico por IA não está implementado; os roteiros atuais são fixos e revisados.

## Próximas versões

- **V2**: tutor socrático gerado por IA, fluxogramas interativos, simulados configuráveis por assunto e por tipo, mais roteiros e mais frases revisadas.
- **V3**: importação de TXT/PDF/imagens (com OCR e revisão manual antes da análise) e biblioteca de questões salvas.
- **V4**: sintaxe, concordância, regência, crase, pontuação, ortografia, interpretação de texto e questões por banca (com fonte confiável). Analogias em Java.
