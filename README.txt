PARES BRASPRESS - GERADOR DE PARES DACTE + DANFE

OBJETIVO
- Ler uma ou mais faturas PDF (nome iniciando com "fatura").
- Conciliar os pares DACTE + DANFE na ordem de cada fatura.
- Exibir em tela os problemas de conciliacao encontrados.
- Gerar PDF(s) de impressao por fatura conforme a opcao escolhida no menu.
- Gerar um CSV com dados extraidos dos DACTEs.
- Extrair numero do CTE e apenas o CEP do destinatario diretamente dos DACTEs (independente da fatura).

COMO O PAREAMENTO FUNCIONA
- AWB (na fatura, coluna NUMERO AWB) -> DACTE pelo campo interno NUMERO do PDF.
- NOTA FISCAL (na fatura, coluna NOTA FISCAL) -> DANFE pelo numero no nome do arquivo.
  Exemplo: DANFE_4682.pdf

REQUISITO DE NOME DAS FATURAS
- As faturas devem ser PDF com prefixo "fatura".
  Exemplos validos:
  - fatura.pdf
  - fatura_abril.pdf
  - fatura_48405991.pdf

ESTRUTURA DO PROJETO
- input\
  - fatura*.pdf
  - dactes e danfes\ (todos os PDFs DACTE e DANFE)
- output\ (arquivos gerados)
- gerar_pares_impressao.bat
- gerar_pares_impressao.py
- .offline_runtime\ (runtime Python local, quando preparado)

EXECUCAO (MODO PADRAO)
1) No portal Braspress, abra a tela/listagem dos documentos e execute o codigo de download.txt no console do navegador (F12 -> Console).
2) Aguarde os downloads de DACTE e DANFE finalizarem.
3) Coloque as faturas em input\ com nome iniciando por "fatura".
4) Copie os PDFs DACTE/DANFE para input\dactes e danfes\
5) Execute gerar_pares_impressao.bat
6) O sistema faz a analise inicial, mostra na tela os problemas de conciliacao e apresenta o menu:
   - 1 - Refazer analise
   - 2 - Imprimir pares na ordem da(s) fatura(s)
   - 3 - Imprimir PDF apenas CTEs
   - 4 - Imprimir PDF apenas com as NFs
    - 5 - Extrair CEP do destinatario
    - 6 - Sair
7) As opcoes 1, 2, 3, 4 e 5 retornam ao menu ao final da execucao.

SAIDA GERADA
- Para multiplas faturas:
  - output\<nome_da_fatura>\impressao_pares_ordenada.pdf
  - output\<nome_da_fatura>\relatorio_conciliacao.txt
  - output\<nome_da_fatura>\impressao_ctes.pdf
  - output\<nome_da_fatura>\relatorio_ctes.txt
  - output\<nome_da_fatura>\impressao_nfs.pdf
  - output\<nome_da_fatura>\relatorio_nfs.txt
- Para uma unica fatura:
  - output\impressao_pares_ordenada.pdf
  - output\relatorio_conciliacao.txt
  - output\impressao_ctes.pdf
  - output\relatorio_ctes.txt
  - output\impressao_nfs.pdf
  - output\relatorio_nfs.txt
- Sempre:
  - output\dactes.csv
  - output\dactes_ceps.csv

CSV DACTES (output\dactes.csv)
Campos exportados:
- Numero NF
- Numero Conhecimento
- Nome Destinatario
- Data de Emissao
- Cidade Origem
- UF Origem
- Cidade Destino
- UF Destino
- Valor da Mercadoria
- Peso da Mercadoria (Kg)

CSV CEPS (output\dactes_ceps.csv)
Campos exportados:
- Arquivo PDF
- Numero Conhecimento
- CEP Destinatario

Observacao:
- A opcao "Extrair CEPs" usa apenas os PDFs DACTE de input\dactes e danfes\ e nao depende da existencia de arquivo de fatura.

AMBIENTE WINDOWS RESTRITO (SEM ADMIN / SEM DOWNLOAD)
- O projeto roda sem permissao de administrador.
- Tudo e criado e usado apenas dentro da pasta do projeto.
- Se o runtime local estiver ausente ou invalido, o .bat tenta reconstruir automaticamente.
- Para maquina sem internet e sem Python instalado:
  1) Prepare o projeto em uma maquina de apoio (com Python e pypdf disponiveis).
  2) Gere .offline_runtime (automaticamente no primeiro uso, ou via montar_runtime_offline.bat).
  3) Copie a pasta completa do projeto para a maquina restrita.
  4) Execute gerar_pares_impressao.bat na maquina restrita.

OBSERVACOES
- A analise inicial mostra em tela as faltas de DACTE e DANFE por ordem da fatura.
- Se faltar algum DACTE ou DANFE, o relatorio da fatura aponta a linha com problema.
- O PDF de pares inclui apenas pares completos.
- O PDF apenas CTEs inclui somente os CTEs encontrados para as linhas da fatura.
- O PDF apenas NFs inclui somente as DANFEs encontradas para as linhas da fatura.
- O arquivo output\dactes.csv e regravado a cada execucao.
