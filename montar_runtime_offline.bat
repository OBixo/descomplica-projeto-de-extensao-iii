@echo off
setlocal

cd /d "%~dp0"

echo [1/4] Detectando Python base...
where py >nul 2>nul
if %errorlevel%==0 (
    set "PY_BASE=py -3"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PY_BASE=python"
    ) else (
        echo [ERRO] Python nao encontrado nesta maquina.
        pause
        exit /b 1
    )
)

echo [2/4] Criando runtime virtual local em .offline_runtime ...
%PY_BASE% -m venv "%~dp0.offline_runtime"
if errorlevel 1 (
    echo [ERRO] Falha ao criar .offline_runtime
    pause
    exit /b 1
)

echo [3/4] Copiando pypdf do Python atual para o runtime offline...
%PY_BASE% "%~dp0montar_runtime_offline.py" "%~dp0.offline_runtime"
if errorlevel 1 (
    echo [ERRO] pypdf nao encontrado no Python base desta maquina.
    echo Instale pypdf nesta maquina de preparacao e rode novamente.
    pause
    exit /b 1
)

echo [4/4] Validando runtime offline...
"%~dp0.offline_runtime\Scripts\python.exe" -c "import pypdf; print('pypdf', pypdf.__version__)"
if errorlevel 1 (
    echo [ERRO] Runtime offline criado, mas pypdf nao carregou.
    pause
    exit /b 1
)

echo.
echo Runtime offline pronto em: "%~dp0.offline_runtime"
echo Agora copie esta pasta inteira para a maquina restrita e execute gerar_pares_impressao.bat
echo.
pause
