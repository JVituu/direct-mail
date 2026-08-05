# Empacotamento do Mala Direta

Este projeto usa PyInstaller para gerar uma versao executavel para Windows.

## Como gerar o executavel

No PowerShell, dentro da pasta do projeto:

```powershell
.\scripts\build_exe.ps1 -Clean
```

Se o PowerShell bloquear scripts locais:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_exe.ps1 -Clean
```

O executavel sera gerado em:

```text
dist\MalaDireta\Mala Direta.exe
```

O icone do aplicativo fica em:

```text
assets\mala_direta_rb_oficial.ico
```

Esse arquivo e usado na janela, na barra de tarefas e no executavel gerado pelo PyInstaller.

Para uma geracao mais rapida sem rodar testes:

```powershell
.\scripts\build_exe.ps1 -Clean -SkipTests
```

## Como entregar para outra maquina

Envie a pasta inteira:

```text
dist\MalaDireta
```

O usuario deve abrir:

```text
Mala Direta.exe
```

Nao envie apenas o `.exe` sozinho, porque a pasta tambem contem arquivos internos do PySide6, Python e dependencias do aplicativo.

## Como criar atalho na area de trabalho

Dentro da pasta enviada ao usuario, execute:

```text
Criar atalho Mala Direta.cmd
```

Esse comando cria um atalho na area de trabalho apontando para o executavel correto, com a pasta `dist\MalaDireta` como diretorio inicial e com o icone oficial do RB.

Nao arraste apenas o `.exe` para a area de trabalho. O aplicativo precisa da pasta `_internal` ao lado para abrir corretamente.

## Windows Defender

Executaveis criados por PyInstaller podem ser sinalizados como suspeitos quando ainda nao possuem assinatura digital.

Para reduzir falsos positivos, o build deste projeto nao usa UPX/compactacao. Se o Windows ainda bloquear o arquivo durante testes internos, revise o alerta em `Seguranca do Windows > Protecao contra virus e ameacas > Historico de protecao` e permita somente este aplicativo se voce tiver acabado de gerar o executavel a partir do codigo do projeto.

Para distribuicao para usuarios externos, o ideal e assinar digitalmente o executavel ou criar um instalador assinado.

## Onde fica o banco SQLite

Na versao de desenvolvimento, o banco continua em:

```text
data\mala_direta.sqlite3
```

Na versao empacotada em `.exe`, o banco e criado automaticamente em:

```text
%LOCALAPPDATA%\MalaDireta\mala_direta.sqlite3
```

Exemplo:

```text
C:\Users\NomeDoUsuario\AppData\Local\MalaDireta\mala_direta.sqlite3
```

Isso evita erro de permissao quando o programa estiver em `Program Files`, pendrive, OneDrive ou outro disco.

## Variaveis opcionais

Para testes ou suporte tecnico, o caminho do banco pode ser sobrescrito:

```powershell
$env:MALA_DIRETA_DATABASE_PATH="D:\dados\mala_direta.sqlite3"
```

Ou apenas a pasta de dados:

```powershell
$env:MALA_DIRETA_DATA_DIR="D:\dados\MalaDireta"
```

Se essas variaveis nao existirem, o sistema escolhe o local automaticamente.
