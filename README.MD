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

## Distribution

Planned methods for delivering the application to the user:

1. Upload the installer or executable to MediaFire.
2. Transfer via USB.
3. Upload the program to OneDrive.

## Documentation

The detailed architectural overview is in `docs/ARCHITECTURE.md`.
