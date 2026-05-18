from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pypdf import PdfReader, PdfWriter


CSV_FIELDS = [
    "numero_nf",
    "numero_conhecimento",
    "nome_destinatario",
    "data_emissao",
    "cidade_origem",
    "uf_origem",
    "cidade_destino",
    "uf_destino",
    "valor_mercadoria",
    "peso_mercadoria",
]

CSV_HEADERS = [
    "Número NF",
    "Número Conhecimento",
    "Nome Destinatário",
    "Data de Emissão",
    "Cidade Origem",
    "UF Origem",
    "Cidade Destino",
    "UF Destino",
    "Valor da Mercadoria",
    "Peso da Mercadoria (Kg)",
]


INVOICE_LINE_RE = re.compile(
    r"^\s*(\d{6,})\s+\S+\s+\S+\s+\d{2}/\d{2}/\d{4}\s+[\d.,]+\s+(\d{3,})\b",
    re.IGNORECASE,
)


def normalize_number(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    return digits.lstrip("0") or "0"


def extract_pairs_from_invoice(invoice_path: Path) -> List[Tuple[str, str, int, str]]:
    reader = PdfReader(str(invoice_path))
    pairs: List[Tuple[str, str, int, str]] = []

    for page_index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if "chave cte" in line.lower():
                continue

            match = INVOICE_LINE_RE.match(line)
            if not match:
                continue

            awb = match.group(1)
            nota_fiscal = match.group(2)
            pairs.append((awb, nota_fiscal, page_index, line))

    return pairs


def extract_dacte_number(text: str) -> Optional[str]:
    patterns = [
        re.compile(
            r"MODELO\s+S[ÉE]RIE\s+N[ÚU]MERO[^\n]*\n\s*\d+\s+\d+\s+(\d{6,10})",
            re.IGNORECASE,
        ),
        re.compile(r"N[ÚU]MERO[^\d]{0,20}(\d{6,10})", re.IGNORECASE),
    ]

    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return re.sub(r"\D", "", match.group(1))

    # Fallback: pega o primeiro numero com 6-10 digitos no topo do documento.
    top_text = "\n".join(text.splitlines()[:50])
    fallback = re.search(r"\b(\d{6,10})\b", top_text)
    if fallback:
        return fallback.group(1)

    return None


def extract_dacte_info(pdf_path: Path) -> Optional[Dict[str, str]]:
    """Extrai informações do DACTE para exportação CSV."""
    try:
        reader = PdfReader(str(pdf_path))
        text = "\n".join((page.extract_text() or "") for page in reader.pages[:3])
    except Exception as exc:
        print(f"[ERRO] Falha ao ler DACTE {pdf_path.name}: {exc}")
        return None

    # Número do conhecimento (CT-e Nº)
    numero_conhecimento = extract_dacte_number(text) or ""

    # Número da nota fiscal (NF-e doc originário: NFE Chave : ... série / nro)
    nfe_match = re.search(
        r"NFE\s+Chave\s*:\s*\S+\s+(\d+)\s*/\s*(\d+)",
        text,
        re.IGNORECASE,
    )
    numero_nf = ""
    if nfe_match:
        numero_nf = str(int(nfe_match.group(2)))  # remove zeros à esquerda

    # Nome do destinatário
    dest_match = re.search(
        r"DESTINAT[AÁ]RIO\s+(.+?)(?:\s{2,}|\n)",
        text,
        re.IGNORECASE,
    )
    nome_destinatario = dest_match.group(1).strip() if dest_match else ""

    # Data de emissão
    data_match = re.search(
        r"MODELO\s+S[ÉE]RIE\s+N[ÚU]MERO[^\n]*\n\s*\d+\s+\d+\s+\d+\s+\S+\s+(\d{2}/\d{2}/\d{4})",
        text,
        re.IGNORECASE,
    )
    data_emissao = data_match.group(1) if data_match else ""

    # Cidade/UF de origem e destino
    cidade_origem = uf_origem = cidade_destino = uf_destino = ""
    orig_block = re.search(
        r"ORIGEM DA PRESTA[ÇC][ÃA]O[^\n]*\n([^\n]+)",
        text,
        re.IGNORECASE,
    )
    if orig_block:
        line = orig_block.group(1)
        # Matches CITY / UF — city name allows single spaces between words only
        city_uf_pairs = re.findall(
            r"([A-ZÁÉÍÓÚÀÂÊÔÃÕÇ][A-ZÁÉÍÓÚÀÂÊÔÃÕÇ]*(?:\s[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ]+)*)\s*/\s*([A-Z]{2})",
            line,
            re.IGNORECASE,
        )
        if len(city_uf_pairs) >= 1:
            cidade_origem = city_uf_pairs[0][0].strip()
            uf_origem = city_uf_pairs[0][1].strip()
        if len(city_uf_pairs) >= 2:
            cidade_destino = city_uf_pairs[1][0].strip()
            uf_destino = city_uf_pairs[1][1].strip()

    # Peso e valor da mercadoria — linha de resumo (CTe Nº ... PESO BRUTO ... VALOR TOTAL DA CARGA)
    valor_mercadoria = ""
    peso_mercadoria = ""
    summary_match = re.search(
        r"CTe\s+N(?:[ÚU]MERO|[º°O])[^\n]*VALOR TOTAL DA CARGA[^\n]*\n([^\n]+)",
        text,
        re.IGNORECASE,
    )
    if summary_match:
        parts = re.split(r"\s{2,}", summary_match.group(1).strip())
        # Ordem: CT-e Nº, RNTRC, VALOR A RECEBER, VOLUMES (UN), PESO BRUTO (Kg), VALOR TOTAL DA CARGA
        if len(parts) >= 5:
            peso_mercadoria = parts[4]
        if len(parts) >= 6:
            valor_mercadoria = parts[5]

    # Fallback: valor da mercadoria da seção PRODUTO PREDOMINANTE
    if not valor_mercadoria:
        valor_fallback = re.search(
            r"PRODUTO PREDOMINANTE[^\n]*\n[^\n]*?(\d[\d.]*,\d{2})\s*(?:\n|$)",
            text,
            re.IGNORECASE,
        )
        if valor_fallback:
            valor_mercadoria = valor_fallback.group(1)

    # Fallback: peso da mercadoria da seção PESO BRUTO
    if not peso_mercadoria:
        peso_fallback = re.search(
            r"PESO BRUTO \(Kg\)[^\n]*\n\s*([\d,]+)",
            text,
            re.IGNORECASE,
        )
        if peso_fallback:
            peso_mercadoria = peso_fallback.group(1)

    return {
        "numero_nf": numero_nf,
        "numero_conhecimento": numero_conhecimento,
        "nome_destinatario": nome_destinatario,
        "data_emissao": data_emissao,
        "cidade_origem": cidade_origem,
        "uf_origem": uf_origem,
        "cidade_destino": cidade_destino,
        "uf_destino": uf_destino,
        "valor_mercadoria": valor_mercadoria,
        "peso_mercadoria": peso_mercadoria,
    }


def export_dactes_to_csv(folder: Path, csv_path: Path) -> int:
    """Exporta informações de todos os DACTEs da pasta para um CSV."""
    rows = []
    for pdf_path in sorted(folder.glob("*.pdf")):
        if "DACTE" not in pdf_path.name.upper():
            continue
        info = extract_dacte_info(pdf_path)
        if info:
            rows.append(info)

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writerow(dict(zip(CSV_FIELDS, CSV_HEADERS)))
        writer.writerows(rows)

    return len(rows)


def index_dactes(folder: Path) -> Tuple[Dict[str, Path], Dict[str, List[Path]]]:
    unique_index: Dict[str, Path] = {}
    duplicates: Dict[str, List[Path]] = defaultdict(list)

    for pdf_path in sorted(folder.glob("*.pdf")):
        if "DACTE" not in pdf_path.name.upper():
            continue

        try:
            reader = PdfReader(str(pdf_path))
            text = "\n".join((page.extract_text() or "") for page in reader.pages[:2])
            number = extract_dacte_number(text)
        except Exception as exc:
            print(f"[ERRO] Falha ao ler DACTE {pdf_path.name}: {exc}")
            continue

        if not number:
            print(f"[AVISO] Nao foi possivel extrair NÚMERO do DACTE: {pdf_path.name}")
            continue

        key = normalize_number(number)
        if key in unique_index:
            duplicates[key].append(pdf_path)
        else:
            unique_index[key] = pdf_path

    return unique_index, duplicates


def index_danfes(folder: Path) -> Tuple[Dict[str, Path], Dict[str, List[Path]]]:
    unique_index: Dict[str, Path] = {}
    duplicates: Dict[str, List[Path]] = defaultdict(list)

    for pdf_path in sorted(folder.glob("*.pdf")):
        upper_name = pdf_path.name.upper()
        if "DANFE" not in upper_name:
            continue

        match = re.search(r"DANFE[_\-\s]?(\d+)", upper_name, re.IGNORECASE)
        if not match:
            print(f"[AVISO] Nome DANFE fora do padrao esperado: {pdf_path.name}")
            continue

        nota = match.group(1)
        key = normalize_number(nota)
        if key in unique_index:
            duplicates[key].append(pdf_path)
        else:
            unique_index[key] = pdf_path

    return unique_index, duplicates


def evaluate_pair_statuses(
    pairs: List[Tuple[str, str, int, str]],
    dacte_index: Dict[str, Path],
    danfe_index: Dict[str, Path],
):
    statuses = []
    for order, (awb, nf, page_index, source_line) in enumerate(pairs, start=1):
        awb_key = normalize_number(awb)
        nf_key = normalize_number(nf)

        dacte_path = dacte_index.get(awb_key)
        danfe_path = danfe_index.get(nf_key)
        missing = []
        if not dacte_path:
            missing.append(f"DACTE(AWB={awb})")
        if not danfe_path:
            missing.append(f"DANFE(NF={nf})")

        statuses.append(
            {
                "order": order,
                "awb": awb,
                "nf": nf,
                "page_index": page_index,
                "source_line": source_line,
                "dacte_path": dacte_path,
                "danfe_path": danfe_path,
                "missing": missing,
            }
        )

    return statuses


def print_analysis_summary(
    invoice_name: str,
    pairs: List[Tuple[str, str, int, str]],
    statuses: List[Dict[str, object]],
) -> None:
    print(f"Fatura: {invoice_name}")
    print(f"  Linhas validas: {len(pairs)}")

    missing_count = 0
    complete_count = 0
    for status in statuses:
        missing = status["missing"]
        if missing:
            missing_count += 1
            print(
                f"[FALTA] Ordem {status['order']} | Pag {status['page_index']} | "
                f"AWB={status['awb']} | NF={status['nf']} | "
                f"Ausente: {', '.join(missing)}"
            )
            print(f"         Linha fatura: {status['source_line']}")
        else:
            complete_count += 1

    if missing_count == 0:
        print("  Nenhum problema de conciliacao encontrado.")

    print(f"  Pares completos: {complete_count}")
    print(f"  Linhas com falta: {missing_count}")


def write_pdf(document_paths: List[Path], output_path: Path) -> None:
    if not document_paths:
        raise RuntimeError("Nenhum documento encontrado para gerar o PDF final.")

    writer = PdfWriter()
    for document_path in document_paths:
        writer.append(str(document_path))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as output_file:
        writer.write(output_file)
    writer.close()


def generate_pairs_pdf(
    pairs: List[Tuple[str, str, int, str]],
    statuses: List[Dict[str, object]],
    output_path: Path,
    report_path: Path,
) -> int:
    document_paths: List[Path] = []
    missing_lines: List[str] = []

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as report:
        report.write("Relatorio de conciliacao DACTE + DANFE\n")
        report.write("=" * 70 + "\n")

        for status in statuses:
            missing = status["missing"]
            if missing:
                msg = (
                    f"[FALTA] Ordem {status['order']} | Pag {status['page_index']} | "
                    f"AWB={status['awb']} | NF={status['nf']} | Ausente: {', '.join(missing)}"
                )
                print(msg)
                report.write(msg + "\n")
                report.write(f"         Linha fatura: {status['source_line']}\n")
                missing_lines.append(msg)
                continue

            document_paths.append(status["dacte_path"])
            document_paths.append(status["danfe_path"])
            report.write(
                f"[OK] Ordem {status['order']:03d} | AWB={status['awb']} -> {status['dacte_path'].name} | "
                f"NF={status['nf']} -> {status['danfe_path'].name}\n"
            )

        if not document_paths:
            report.write("\nNenhum par completo foi encontrado.\n")

        report.write("\n" + "=" * 70 + "\n")
        report.write(f"Total de linhas da fatura lidas: {len(pairs)}\n")
        report.write(f"Pares completos adicionados: {len(document_paths) // 2}\n")
        report.write(f"Linhas com falta: {len(missing_lines)}\n")

    if not document_paths:
        raise RuntimeError("Nenhum par completo encontrado para gerar o PDF final.")

    write_pdf(document_paths, output_path)
    return len(document_paths) // 2


def generate_single_document_pdf(
    pairs: List[Tuple[str, str, int, str]],
    statuses: List[Dict[str, object]],
    output_path: Path,
    report_path: Path,
    document_type: str,
) -> int:
    document_paths: List[Path] = []
    missing_lines: List[str] = []

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as report:
        report.write(f"Relatorio de impressao apenas {document_type}\n")
        report.write("=" * 70 + "\n")

        for status in statuses:
            if document_type == "CTEs":
                target_path = status["dacte_path"]
                missing_label = f"DACTE(AWB={status['awb']})"
                key_value = status["awb"]
            else:
                target_path = status["danfe_path"]
                missing_label = f"DANFE(NF={status['nf']})"
                key_value = status["nf"]

            if not target_path:
                msg = (
                    f"[FALTA] Ordem {status['order']} | Pag {status['page_index']} | "
                    f"Referencia={key_value} | Ausente: {missing_label}"
                )
                print(msg)
                report.write(msg + "\n")
                report.write(f"         Linha fatura: {status['source_line']}\n")
                missing_lines.append(msg)
                continue

            document_paths.append(target_path)
            report.write(
                f"[OK] Ordem {status['order']:03d} | Referencia={key_value} -> {target_path.name}\n"
            )

        if not document_paths:
            report.write(f"\nNenhum PDF de {document_type} foi encontrado.\n")

        report.write("\n" + "=" * 70 + "\n")
        report.write(f"Total de linhas da fatura lidas: {len(pairs)}\n")
        report.write(f"PDFs adicionados: {len(document_paths)}\n")
        report.write(f"Linhas com falta: {len(missing_lines)}\n")

    if not document_paths:
        raise RuntimeError(f"Nenhum PDF de {document_type} encontrado para gerar o arquivo final.")

    write_pdf(document_paths, output_path)
    return len(document_paths)


def resolve_invoice_output_paths(
    invoice_path: Path,
    invoice_count: int,
    output_root_dir: Path,
    output_filename: str,
    report_filename: str,
) -> Tuple[Path, Path]:
    if invoice_count == 1:
        return output_root_dir / output_filename, output_root_dir / report_filename

    invoice_folder = output_root_dir / invoice_path.stem
    return invoice_folder / output_filename, invoice_folder / report_filename


def load_context(
    faturas_dir: Path,
    folder_path: Path,
) -> Tuple[List[Path], Dict[Path, List[Tuple[str, str, int, str]]], Dict[str, Path], Dict[str, List[Path]], Dict[str, Path], Dict[str, List[Path]]]:
    if not faturas_dir.exists():
        raise RuntimeError(f"Pasta de faturas nao encontrada: {faturas_dir}")

    invoice_files = sorted(
        p for p in faturas_dir.glob("*.pdf") if p.stem.lower().startswith("fatura")
    )
    if not invoice_files:
        raise RuntimeError(
            f"Nenhum arquivo com prefixo 'fatura' encontrado em: {faturas_dir}\n"
            "Renomeie sua(s) fatura(s) para comecar com 'fatura' (ex: fatura.pdf, fatura_abril.pdf)."
        )

    if not folder_path.exists():
        raise RuntimeError(f"Pasta nao encontrada: {folder_path}")

    pairs_by_invoice: Dict[Path, List[Tuple[str, str, int, str]]] = {}
    for invoice_path in invoice_files:
        pairs_by_invoice[invoice_path] = extract_pairs_from_invoice(invoice_path)

    dacte_index, dacte_duplicates = index_dactes(folder_path)
    danfe_index, danfe_duplicates = index_danfes(folder_path)
    return (
        invoice_files,
        pairs_by_invoice,
        dacte_index,
        dacte_duplicates,
        danfe_index,
        danfe_duplicates,
    )


def run_analysis(
    invoice_files: List[Path],
    pairs_by_invoice: Dict[Path, List[Tuple[str, str, int, str]]],
    dacte_index: Dict[str, Path],
    dacte_duplicates: Dict[str, List[Path]],
    danfe_index: Dict[str, Path],
    danfe_duplicates: Dict[str, List[Path]],
    csv_path: Path,
    folder_path: Path,
) -> int:
    print(f"Indexando DACTEs em: {folder_path}")
    print(f"DACTEs indexados por NUMERO interno: {len(dacte_index)}")
    if dacte_duplicates:
        print(f"[AVISO] DACTEs duplicados por NUMERO: {len(dacte_duplicates)}")

    print(f"Indexando DANFEs em: {folder_path}")
    print(f"DANFEs indexados por numero no nome: {len(danfe_index)}")
    if danfe_duplicates:
        print(f"[AVISO] DANFEs duplicados por numero: {len(danfe_duplicates)}")

    print("Analisando conciliacao das faturas...")
    total_complete = 0
    total_missing = 0

    for invoice_path in invoice_files:
        pairs = pairs_by_invoice[invoice_path]
        statuses = evaluate_pair_statuses(pairs, dacte_index, danfe_index)
        print_analysis_summary(invoice_path.name, pairs, statuses)
        total_complete += sum(1 for status in statuses if not status["missing"])
        total_missing += sum(1 for status in statuses if status["missing"])

    print(f"Resumo geral: {len(invoice_files)} fatura(s), {total_complete} pares completos, {total_missing} linha(s) com falta.")
    print("Exportando informacoes dos DACTEs para CSV...")
    csv_count = export_dactes_to_csv(folder_path, csv_path)
    print(f"CSV gerado com {csv_count} registros: {csv_path}")
    return 0


def run_generation(
    mode: str,
    invoice_files: List[Path],
    pairs_by_invoice: Dict[Path, List[Tuple[str, str, int, str]]],
    dacte_index: Dict[str, Path],
    danfe_index: Dict[str, Path],
    output_root_dir: Path,
) -> int:
    generated = 0
    failed = 0

    if mode == "pares":
        output_filename = "impressao_pares_ordenada.pdf"
        report_filename = "relatorio_conciliacao.txt"
        description = "pares na ordem da fatura"
    elif mode == "ctes":
        output_filename = "impressao_ctes.pdf"
        report_filename = "relatorio_ctes.txt"
        description = "apenas CTEs"
    else:
        output_filename = "impressao_nfs.pdf"
        report_filename = "relatorio_nfs.txt"
        description = "apenas NFs"

    print(f"Gerando PDF(s) de {description}...")
    for invoice_path in invoice_files:
        pairs = pairs_by_invoice[invoice_path]
        statuses = evaluate_pair_statuses(pairs, dacte_index, danfe_index)
        output_path, report_path = resolve_invoice_output_paths(
            invoice_path=invoice_path,
            invoice_count=len(invoice_files),
            output_root_dir=output_root_dir,
            output_filename=output_filename,
            report_filename=report_filename,
        )

        print(f"Processando fatura: {invoice_path.name}")
        print(f"  Linhas validas: {len(pairs)}")

        if not pairs:
            print(f"[ERRO] Nao foi possivel extrair pares AWB/NF da fatura: {invoice_path.name}")
            failed += 1
            continue

        try:
            if mode == "pares":
                included = generate_pairs_pdf(pairs, statuses, output_path, report_path)
                print(f"  Concluido: {included} pares adicionados.")
            elif mode == "ctes":
                included = generate_single_document_pdf(
                    pairs, statuses, output_path, report_path, "CTEs"
                )
                print(f"  Concluido: {included} CTE(s) adicionados.")
            else:
                included = generate_single_document_pdf(
                    pairs, statuses, output_path, report_path, "NFs"
                )
                print(f"  Concluido: {included} NF(s) adicionadas.")
        except Exception as exc:
            print(f"[ERRO] Falha ao gerar PDF da fatura {invoice_path.name}: {exc}")
            failed += 1
            continue

        generated += 1
        print(f"  PDF final: {output_path}")
        print(f"  Relatorio: {report_path}")

    if generated == 0:
        print("[ERRO] Nao foi possivel gerar nenhum PDF de saida.")
        return 1

    print(f"Resumo: {generated} fatura(s) gerada(s), {failed} com falha.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Concilia DACTE e DANFE na ordem da fatura e gera PDF(s) "
            "com os pares para impressao."
        )
    )
    parser.add_argument(
        "--pasta-faturas",
        default="input",
        help="Pasta onde buscar PDFs com prefixo 'fatura'",
    )
    parser.add_argument(
        "--pasta",
        default="input/dactes e danfes",
        help="Pasta com os PDFs DACTE e DANFE",
    )
    parser.add_argument(
        "--saida",
        default="output/impressao_pares_ordenada.pdf",
        help="PDF final de saida",
    )
    parser.add_argument(
        "--relatorio",
        default="output/relatorio_conciliacao.txt",
        help="Arquivo de relatorio de conciliacao",
    )
    parser.add_argument(
        "--csv",
        default="output/dactes.csv",
        help="Arquivo CSV com informacoes dos DACTEs",
    )
    parser.add_argument(
        "--modo",
        default="pares",
        choices=["analisar", "pares", "ctes", "nfs"],
        help="Modo de execucao: analisar, pares, ctes ou nfs",
    )

    args = parser.parse_args()

    faturas_dir = Path(args.pasta_faturas).resolve()
    folder_path = Path(args.pasta).resolve()
    output_root_dir = Path(args.saida).resolve().parent
    csv_path = Path(args.csv).resolve()

    try:
        (
            invoice_files,
            pairs_by_invoice,
            dacte_index,
            dacte_duplicates,
            danfe_index,
            danfe_duplicates,
        ) = load_context(faturas_dir, folder_path)
    except RuntimeError as exc:
        print(f"[ERRO] {exc}")
        return 1

    if args.modo == "analisar":
        return run_analysis(
            invoice_files=invoice_files,
            pairs_by_invoice=pairs_by_invoice,
            dacte_index=dacte_index,
            dacte_duplicates=dacte_duplicates,
            danfe_index=danfe_index,
            danfe_duplicates=danfe_duplicates,
            csv_path=csv_path,
            folder_path=folder_path,
        )

    return run_generation(
        mode=args.modo,
        invoice_files=invoice_files,
        pairs_by_invoice=pairs_by_invoice,
        dacte_index=dacte_index,
        danfe_index=danfe_index,
        output_root_dir=output_root_dir,
    )


if __name__ == "__main__":
    sys.exit(main())
