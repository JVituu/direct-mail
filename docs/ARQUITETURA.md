# Arquitetura

Este projeto usa uma separação inspirada em Clean Architecture para manter a regra de negócio simples, testável e independente da interface gráfica ou do banco de dados.

## Regra de dependência

As dependências devem apontar para dentro:

```text
presentation -> application -> domain
infrastructure -> application -> domain
```

A camada `domain` não deve importar nada de PySide6, pandas, openpyxl, SQLite ou PyInstaller.

## Fluxo principal

```text
Tela PySide6
  -> ViewModel/Controller
  -> Caso de uso
  -> Contrato de repositório
  -> Implementação SQLite ou leitor XLSX
```

## Camada domain

Responsabilidade:

- Representar conceitos centrais do negócio.
- Definir entidades como convidado, lista de convidados e seleção.
- Definir contratos de repositório quando eles forem parte do negócio.
- Validar regras que não dependem de tela, banco ou planilha.

Não deve conter:

- Código de PySide6.
- Código de pandas/openpyxl.
- SQL.
- Caminhos de arquivos.

## Camada application

Responsabilidade:

- Orquestrar os casos de uso.
- Receber dados da interface.
- Chamar contratos de repositório.
- Retornar dados simples para a interface.

Casos de uso previstos:

- Importar planilha.
- Importar múltiplas abas de uma pasta Excel.
- Listar convidados importados.
- Selecionar convidados.
- Criar lista final de convidados.
- Consultar listas salvas.

## Camada infrastructure

Responsabilidade:

- Implementar leitura de arquivos `XLSX`.
- Implementar persistência em SQLite.
- Implementar repositórios concretos.
- Isolar detalhes técnicos externos das camadas internas.

Bibliotecas esperadas nesta camada:

- `sqlite3`
- `pandas`
- `openpyxl`

## Camada presentation

Responsabilidade:

- Construir telas PySide6.
- Coletar ações do usuário.
- Exibir dados retornados pelos casos de uso.
- Mostrar mensagens de erro ou sucesso.

Não deve conter:

- SQL.
- Transformação pesada de planilha.
- Regra de seleção de convidados.
- Decisão de persistência.

## Camada shared

Responsabilidade:

- Centralizar erros compartilhados.
- Centralizar pequenas funções utilitárias realmente comuns.

Essa camada deve ser usada com cuidado para não virar uma pasta genérica demais.

## Banco de dados

O SQLite será usado como banco local da aplicação. A interface gráfica não deve acessar o banco diretamente. Todo acesso ao banco deve passar por casos de uso e repositórios.

No MVP, o banco local é criado em `data/mala_direta.sqlite3` e possui tabelas para importações e convidados importados.

A persistência separa:

- `workbooks`: cada arquivo `.xlsx` importado.
- `imports`: cada aba/sheet do arquivo.
- `guests`: linhas importadas de cada aba, incluindo o `verification_code` criado pelo sistema.
- `guest_identities`: chaves normalizadas de nome, telefone e e-mail usadas para detectar duplicidades.
- `automatic_guests`: cópias independentes dos registros enviados para a Planilha automática.
- `app_settings`: pequenas configurações locais, como o nome da Planilha automática.

Ao excluir uma planilha importada, o workbook, suas abas e suas linhas são removidos do SQLite.

## Planilhas

A leitura de planilhas deve ficar isolada em `app/infrastructure/spreadsheet`. Assim, se no futuro a leitura mudar de pandas para openpyxl puro, a regra de negócio não será afetada.

Para planilhas grandes, a leitura inicial do MVP usa `openpyxl` em modo `read_only`, importando os dados em lotes para o SQLite. A interface exibe os registros por paginação, evitando carregar todos os registros na tabela de uma vez.

O importador detecta a linha de cabeçalho dentro das primeiras linhas da aba. Isso permite ler planilhas com título e observação antes da tabela real, como:

```text
Linha 1: Contatos fictícios — Amigos
Linha 2: Texto de observação
Linha 3: Nome | Endereço | Telefone | Obra / Universo
Linha 4+: Dados
```

Cada aba com tabela é importada como uma sheet visualizável. Abas com colunas típicas de contato, como `Nome`, `Telefone`, `Email` ou `Endereço`, são tratadas como listas selecionáveis. Abas como `Resumo` continuam visíveis, mas não entram no fluxo de seleção de convidados.

A interface organiza a navegação em dois níveis:

- Abas superiores para arquivos `.xlsx` importados e para a Planilha automática.
- Abas inferiores para as sheets/listas do arquivo atual.

A planilha automática de selecionados é formada a partir de cópias dos convidados marcados nas listas selecionáveis e aparece como uma guia superior própria quando houver pelo menos um selecionado.

A exclusão e a renomeação de um workbook são acionadas pela interface através do menu de contexto da aba superior do arquivo. A Planilha automática também usa menu de contexto: renomear altera o nome exibido, e excluir limpa a lista final de convidados selecionados sem remover os arquivos importados.

A edição de células em uma sheet importada altera o registro original em `guests.data_json`. A edição na Planilha automática altera apenas a cópia salva em `automatic_guests.data_json`, mantendo a planilha principal intacta.

Cada linha importada recebe um `verification_code` numérico único, gerado pela aplicação e persistido no SQLite. Esse código é exibido como coluna de sistema, pode ser usado na busca e não faz parte das colunas originais do Excel.

A detecção de duplicidades usa uma tabela auxiliar com identidade normalizada. A comparação prioriza e-mail, depois telefone, depois nome normalizado. Duplicados são apenas sinalizados na coluna `Duplicidade` e na aba superior `Duplicados`; nenhuma linha é excluída, unificada ou alterada automaticamente.

## Testes

Estratégia recomendada:

- Testes de domínio para regras puras.
- Testes de aplicação para casos de uso.
- Testes de infraestrutura para SQLite e leitura de planilhas.
- Testes manuais ou automatizados específicos para a interface PySide6.
