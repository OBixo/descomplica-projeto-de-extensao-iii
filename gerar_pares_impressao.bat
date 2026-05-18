@echo off
setlocal

cd /d "%~dp0"

set "INPUT_DIR=%~dp0input"
set "OUTPUT_DIR=%~dp0output"
set "RUNTIME_DIR=%~dp0.offline_runtime"
set "RUNTIME_EXE=%RUNTIME_DIR%\Scripts\python.exe"

if not exist "%INPUT_DIR%" mkdir "%INPUT_DIR%"
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

echo [1/4] Organizando estrutura input/output...
for %%f in ("%~dp0fatura*.pdf") do (
    if exist "%%~ff" if not exist "%INPUT_DIR%\%%~nxf" move /Y "%%f" "%INPUT_DIR%\%%~nxf" >nul
)
if exist "%~dp0dactes e danfes" if not exist "%INPUT_DIR%\dactes e danfes" move "%~dp0dactes e danfes" "%INPUT_DIR%\dactes e danfes" >nul

set "FATURA_FOUND=0"
for %%f in ("%INPUT_DIR%\fatura*.pdf") do (
    if exist "%%~ff" set "FATURA_FOUND=1"
)
if "%FATURA_FOUND%"=="0" (
    echo [ERRO] Nenhum arquivo com prefixo 'fatura' encontrado em: "%INPUT_DIR%"
    echo Renomeie suas faturas para comecar com 'fatura', por exemplo: fatura.pdf ou fatura_abril.pdf.
    pause
    exit /b 1
)

if not exist "%INPUT_DIR%\dactes e danfes" (
    echo [ERRO] Pasta nao encontrada: "%INPUT_DIR%\dactes e danfes"
    echo Coloque os PDFs DACTE/DANFE nesse caminho e tente novamente.
    pause
    exit /b 1
)

echo [2/4] Localizando Python base para preparar runtime se necessario...
set "PY_BASE="
where py >nul 2>nul
if %errorlevel%==0 (
    set "PY_BASE=py -3"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PY_BASE=python"
    )
)

if not exist "%RUNTIME_EXE%" (
    echo Runtime offline ausente. Tentando montar localmente sem admin...
    call :rebuild_runtime
    if errorlevel 1 (
        pause
        exit /b 1
    )
)

echo [3/4] Validando runtime offline local...
"%RUNTIME_EXE%" -c "import pypdf; print('pypdf ok')" >nul 2>nul
if errorlevel 1 (
    echo [AVISO] Runtime offline invalido. Tentando reconstruir automaticamente...
    call :rebuild_runtime
    if errorlevel 1 (
        pause
        exit /b 1
    )

    "%RUNTIME_EXE%" -c "import pypdf; print('pypdf ok')" >nul 2>nul
    if errorlevel 1 (
        echo [ERRO] Runtime local sem pypdf valido mesmo apos reconstrucao.
        pause
        exit /b 1
    )
)

echo [4/4] Analisando conciliacao...
call :run_python analisar
if errorlevel 1 (
    echo [ERRO] O processo terminou com falha. Veja as mensagens acima.
    pause
    exit /b 1
)

:menu
echo.
echo Problemas de conciliacao e avisos exibidos acima.
echo.
echo 1 - Refazer analise
echo 2 - Imprimir pares na ordem da(s) fatura(s)
echo 3 - Imprimir PDF apenas CTEs
echo 4 - Imprimir PDF apenas com as NFs
echo 5 - Sair
choice /c 12345 /n /m "Digite o numero desejado: "

if errorlevel 5 goto :fim
if errorlevel 4 goto :op_nfs
if errorlevel 3 goto :op_ctes
if errorlevel 2 goto :op_pares
if errorlevel 1 goto :op_analisar

:op_analisar
echo.
echo Refazendo analise...
call :run_python analisar
echo.
pause
goto :menu

:op_pares
echo.
echo Gerando PDF de pares na ordem da(s) fatura(s)...
call :cleanup_root_outputs pares
call :run_python pares
echo.
pause
goto :menu

:op_ctes
echo.
echo Gerando PDF apenas com CTEs...
call :cleanup_root_outputs ctes
call :run_python ctes
echo.
pause
goto :menu

:op_nfs
echo.
echo Gerando PDF apenas com NFs...
call :cleanup_root_outputs nfs
call :run_python nfs
echo.
pause
goto :menu

:fim
echo.
echo Encerrado.

goto :eof

:run_python
"%RUNTIME_EXE%" "%~dp0gerar_pares_impressao.py" --modo %1 --pasta-faturas "%INPUT_DIR%" --pasta "%INPUT_DIR%\dactes e danfes" --saida "%OUTPUT_DIR%\impressao_pares_ordenada.pdf" --relatorio "%OUTPUT_DIR%\relatorio_conciliacao.txt" --csv "%OUTPUT_DIR%\dactes.csv"
exit /b %errorlevel%

:cleanup_root_outputs
if /I "%~1"=="pares" (
    if exist "%OUTPUT_DIR%\impressao_pares_ordenada.pdf" del /q "%OUTPUT_DIR%\impressao_pares_ordenada.pdf" >nul 2>nul
    if exist "%OUTPUT_DIR%\relatorio_conciliacao.txt" del /q "%OUTPUT_DIR%\relatorio_conciliacao.txt" >nul 2>nul
)
if /I "%~1"=="ctes" (
    if exist "%OUTPUT_DIR%\impressao_ctes.pdf" del /q "%OUTPUT_DIR%\impressao_ctes.pdf" >nul 2>nul
    if exist "%OUTPUT_DIR%\relatorio_ctes.txt" del /q "%OUTPUT_DIR%\relatorio_ctes.txt" >nul 2>nul
)
if /I "%~1"=="nfs" (
    if exist "%OUTPUT_DIR%\impressao_nfs.pdf" del /q "%OUTPUT_DIR%\impressao_nfs.pdf" >nul 2>nul
    if exist "%OUTPUT_DIR%\relatorio_nfs.txt" del /q "%OUTPUT_DIR%\relatorio_nfs.txt" >nul 2>nul
)
exit /b 0

:rebuild_runtime
if "%PY_BASE%"=="" (
    echo [ERRO] Sem Python local para montar runtime offline.
    echo Instale Python nesta maquina ou execute o processo em ambiente com Python e pypdf.
    exit /b 1
)

if exist "%RUNTIME_DIR%" rmdir /s /q "%RUNTIME_DIR%"

%PY_BASE% -m venv "%RUNTIME_DIR%"
if errorlevel 1 (
    echo [ERRO] Falha ao criar runtime local em .offline_runtime
    exit /b 1
)

%PY_BASE% "%~dp0montar_runtime_offline.py" "%RUNTIME_DIR%"
if errorlevel 1 (
    echo [ERRO] Nao foi possivel copiar pypdf para o runtime offline.
    echo Garanta que o Python desta maquina tenha pypdf ja instalado.
    exit /b 1
)

exit /b 0
