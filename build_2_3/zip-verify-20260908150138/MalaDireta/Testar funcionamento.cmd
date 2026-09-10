@echo off
setlocal

set "APP_DIR=%~dp0"
set "TEST_DATA=%TEMP%\MalaDiretaSmokeTest_%RANDOM%_%RANDOM%"

mkdir "%TEST_DATA%" >nul 2>nul
set "MALA_DIRETA_DATA_DIR=%TEST_DATA%"

"%APP_DIR%Mala Direta.exe" --smoke-test
set "EXIT_CODE=%ERRORLEVEL%"

if "%EXIT_CODE%"=="0" (
    if exist "%TEST_DATA%\mala_direta.sqlite3" (
        echo Teste OK: aplicativo, recursos e banco de dados carregaram corretamente.
    ) else (
        echo Teste falhou: o banco de dados de teste nao foi criado.
        set "EXIT_CODE=1"
    )
) else (
    echo Teste falhou: o aplicativo nao passou na verificacao automatica.
    echo Confirme se a pasta _internal esta junto do executavel.
)

pause
exit /b %EXIT_CODE%
