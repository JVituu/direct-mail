# Direct-Mail

Desktop application for importing `XLSX` files, viewing guests, and creating a new list containing only the guests selected by the user.

## Objective

The system must allow the user to:

1. Import an `XLSX` spreadsheet.
2. View the guests found in the spreadsheet.
3. Select specific guests.
4. Create a new list with the selected guests.
5. Persist the data locally in SQLite.

## Architecture

The project follows an organizational structure inspired by Clean Architecture. The main principle is to keep business rules independent of the graphical interface, database, and external libraries.

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


### Layers

`domain`
: Contains the business’s core entities, value objects, and contracts. It should not depend on PySide6, pandas, openpyxl, SQLite, or any external details.

`application`
: Contains the system’s use cases, such as importing spreadsheets, listing guests, selecting guests, and creating shortlists.

`infrastructure`
: Contains technical implementations, such as SQLite persistence, reading spreadsheets with pandas/openpyxl, and concrete repositories.

`presentation`
: Contains the desktop interface built with PySide6. This layer calls the use cases but should not contain business rules.

`shared`
: Contains shared utilities and error handling that do not belong exclusively to a single layer.

`main.py`
: The application’s entry point. It should load dependencies and launch the graphical user interface.

## Technologies

1. Python - Programming language.
2. SQLite - Local database.
3. PySide6 - Desktop graphical user interface.
4. pandas - Support for data analysis and transformation.
5. openpyxl - Reading and writing Excel files.
6. PyInstaller - Generation of the `.exe` executable.

## Installation

After creating and activating the virtual environment:

```bash
pip install PySide6
pip install pandas
pip install openpyxl
pip install pyinstaller
pip freeze > requirements.txt
```

SQLite does not need to be installed separately, as it is already part of the standard Python library.

## Executar o MVP

Com o ambiente virtual criado, rode:

```bash
ambiente_config\Scripts\python.exe -m app.main
```

O MVP atual permite:

1. Importar uma planilha `.xlsx`.
2. Manter cada arquivo importado dentro do sistema como uma aba superior.
3. Renomear ou excluir uma planilha importada pelo botão direito na aba superior.
4. Mostrar as abas internas do Excel, como Resumo, Amigos, Família, Jornalistas ou Políticos.
5. Detectar tabelas que possuem título e observação antes do cabeçalho.
6. Gerar um `Código` único do sistema para cada linha importada.
7. Identificar possíveis duplicados entre planilhas importadas.
8. Visualizar os registros com paginação.
9. Buscar texto em qualquer coluna importada ou pelo `Código`.
10. Editar dados importados diretamente na tabela.
11. Filtrar listas/abas pelo botão `Filtros`.
12. Selecionar convidados pela coluna `Selecionado`, por página, por filtro ou pelo botão `Selecionar todos`.
13. Visualizar a planilha automática de selecionados como uma guia superior própria.
14. Exportar os convidados selecionados para um novo `.xlsx`.

No ambiente de desenvolvimento, o banco local é criado automaticamente em `data/mala_direta.sqlite3`.
Na versão `.exe`, o banco é criado automaticamente em `%LOCALAPPDATA%\MalaDireta\mala_direta.sqlite3`.

Arquivos já importados ficam salvos no banco local. Para renomear ou remover um arquivo do sistema, clique com o botão direito na aba superior do arquivo e escolha `Renomear planilha` ou `Excluir planilha`.

A guia superior `Planilha automática` aparece quando existir pelo menos um convidado selecionado. Ela é atualizada em tempo real e também pode ser renomeada ou excluída pelo botão direito. Excluir essa guia limpa a lista final de selecionados, sem remover as planilhas importadas.

As células de dados podem ser editadas com duplo clique ou F2. A Planilha automática guarda uma cópia independente dos nomes selecionados, então alterações feitas nela não modificam a planilha principal. Na planilha principal, linhas selecionadas ficam destacadas em verde.

A coluna `Código` é criada pelo próprio aplicativo durante a importação. Ela não vem do Excel, não é editável e não se repete entre linhas salvas no sistema.

A coluna `Duplicidade` sinaliza possíveis pessoas repetidas usando e-mail, telefone ou nome normalizado. O sistema não apaga nem mescla registros automaticamente; ele apenas mostra a suspeita e cria a aba superior `Duplicados` quando existir algo para revisar.

## Testes

Para rodar os testes automatizados:

```bash
ambiente_config\Scripts\python.exe -m unittest
```

## Distribuição

Para gerar a pasta executável do Windows:

```powershell
.\scripts\build_exe.ps1 -Clean
```

O resultado fica em `dist\MalaDireta\Mala Direta.exe`. Para entregar em outra máquina, envie a pasta inteira `dist\MalaDireta`.

Para criar o atalho correto na área de trabalho, execute `Criar atalho Mala Direta.cmd` dentro da pasta `dist\MalaDireta`. Não arraste apenas o `.exe` para fora da pasta, porque o aplicativo precisa da pasta `_internal` para abrir corretamente.

Mais detalhes estão em [docs/EMPACOTAMENTO_EXE.md](docs/EMPACOTAMENTO_EXE.md).

Planned methods for delivering the application to the user:

1. Upload the installer or executable to MediaFire.
2. Transfer via USB.
3. Upload the program to OneDrive.

## Documentation

The detailed architectural overview is in `docs/ARCHITECTURE.md`.
