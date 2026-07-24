# Mala Direta

Aplicativo desktop para importar arquivos `XLSX`, visualizar convidados e montar uma nova lista apenas com os convidados selecionados pelo usuário.

## Objetivo

O sistema deve permitir que o usuário:

1. Importe uma planilha `XLSX`.
2. Visualize os convidados encontrados na planilha.
3. Selecione convidados específicos.
4. Crie uma nova lista com os convidados selecionados.
5. Persista os dados localmente em SQLite.

## Arquitetura

O projeto segue uma organização inspirada em Clean Architecture. A regra principal é manter as regras de negócio independentes de interface gráfica, banco de dados e bibliotecas externas.

```text
app/
  main.py
  domain/
    entities/
    repositories/
    value_objects/
  application/
    dtos/
    use_cases/
  infrastructure/
    database/
    repositories/
    spreadsheet/
  presentation/
    desktop/
      views/
      viewmodels/
      widgets/
  shared/
    errors/
    utils/
docs/
tests/
```

### Camadas

`domain`
: Contém as entidades, objetos de valor e contratos centrais do negócio. Não deve depender de PySide6, pandas, openpyxl, SQLite ou qualquer detalhe externo.

`application`
: Contém os casos de uso do sistema, como importar planilha, listar convidados, selecionar convidados e criar listas selecionadas.

`infrastructure`
: Contém implementações técnicas, como persistência em SQLite, leitura de planilhas com pandas/openpyxl e repositórios concretos.

`presentation`
: Contém a interface desktop feita com PySide6. Essa camada chama os casos de uso, mas não deve concentrar regra de negócio.

`shared`
: Contém utilitários e erros compartilhados que não pertencem exclusivamente a uma camada.

`main.py`
: Ponto de entrada da aplicação. Deve montar as dependências e iniciar a interface gráfica.

## Tecnologias

1. Python - Linguagem de programação.
2. SQLite - Banco de dados local.
3. PySide6 - Interface gráfica desktop.
4. pandas - Apoio para análise e transformação de dados.
5. openpyxl - Leitura e escrita de arquivos Excel.
6. PyInstaller - Geração do executável `.exe`.

## Instalação

Após criar e ativar o ambiente virtual:

```bash
pip install PySide6
pip install pandas
pip install openpyxl
pip install pyinstaller
pip freeze > requirements.txt
```

O SQLite não precisa ser instalado separadamente, pois já faz parte da biblioteca padrão do Python.

## Distribuição

Formas previstas para entregar o aplicativo ao usuário:

1. Upload do instalador ou executável no MediaFire.
2. Transferência via USB.
3. Upload do programa no OneDrive.

## Documentação

A visão arquitetural detalhada está em `docs/ARQUITETURA.md`.
