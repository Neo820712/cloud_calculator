"""
Read the input Excel, iterate rows with AWS Calculator links,
fetch each estimate, then summarize the output as requested.
"""
import io
import re
from collections import defaultdict
from datetime import date

import pandas as pd

from aws_calculator import extract_urls, fetch_estimate_instances, classify_processor


_SPANISH_MONTHS = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}

_INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')


def month_name_es(d: date) -> str:
    """Return the Spanish month name in lowercase for the given date."""
    return _SPANISH_MONTHS[d.month]


def safe_company_filename(company: str) -> str:
    """Sanitize a company name for use as a filename base.

    Replaces filesystem-invalid characters with '_'. Blank names — or names consisting only of invalid characters — become 'SinEmpresa'.
    """
    name = (company or "").strip()
    if not name:
        return "SinEmpresa"
    name = _INVALID_FILENAME_CHARS.sub("_", name).strip("_ ")
    return name or "SinEmpresa"


def xpa_filename(company: str, d: date) -> str:
    """Build the per-company XPA filename: '{base}_{year}_{month}.xlsx'."""
    return f"{safe_company_filename(company)}_{d.year}_{month_name_es(d)}.xlsx"


def build_xpa_groups(raw_results: list[dict], provider: str) -> dict:
    """Group raw results into one DataFrame per company for XPA output.

    Returns {sanitized_company_base: DataFrame[#, Provider, Instance, Quantity]},
    quantities summed per instance, instances sorted alphabetically, # restarting at 1.
    """
    agg: dict[tuple, int] = defaultdict(int)
    for r in raw_results:
        key = safe_company_filename(r["customer"])
        agg[(key, r["instance"])] += r["count"]

    by_company: dict[str, list] = defaultdict(list)
    for (key, inst), cnt in sorted(agg.items()):
        by_company[key].append((inst, cnt))

    groups: dict = {}
    for key, items in by_company.items():
        rows = []
        for counter, (inst, cnt) in enumerate(items, start=1):
            rows.append({
                "#":        counter,
                "Provider": provider,
                "Instance": inst,
                "Quantity": cnt,
            })
        groups[key] = pd.DataFrame(rows, columns=["#", "Provider", "Instance", "Quantity"])
    return groups


def col_letter_to_index(letters: str) -> int:
    result = 0
    for ch in letters.upper():
        result = result * 26 + (ord(ch) - ord('A') + 1)
    return result - 1


def process_excel_file(
    file_bytes: bytes,
    link_column: str,
    header_row: int,
    cloud_provider: str,
    customer_column: str = "",
    summarize_by: str = "none",   # "none" | "company" | "total" | "xpa"
    progress_cb=None,
) -> "pd.DataFrame | dict":
    """
    Args:
        link_column     : column letter with calculator URLs (e.g. 'J')
        header_row      : 1-based header row number (6 for sample files)
        cloud_provider  : e.g. 'AWS'
        customer_column : column letter with company/customer name (e.g. 'E')
        summarize_by    : 'none' → one row per opportunity×instance
                          'company' → aggregate by (company, instance)
                          'total' → aggregate all instances across every row
                          'xpa' → dict {empresa: DataFrame[#,Provider,Instance,Quantity]} (un archivo por empresa)
    """
    pandas_header = (header_row - 1) if header_row > 0 else None
    df = pd.read_excel(io.BytesIO(file_bytes), header=pandas_header, dtype=str)

    link_idx     = col_letter_to_index(link_column)
    customer_idx = col_letter_to_index(customer_column) if customer_column.strip() else None

    # ── Collect rows with calculator links ────────────────────────────────────
    rows_to_process = []
    for row_idx, row in df.iterrows():
        if link_idx >= len(row):
            continue
        cell = str(row.iloc[link_idx]) if not pd.isna(row.iloc[link_idx]) else ''
        urls = extract_urls(cell)
        if not urls:
            continue

        customer = ""
        if customer_idx is not None and customer_idx < len(row):
            val = row.iloc[customer_idx]
            customer = str(val).strip() if not pd.isna(val) else ""
            if customer.lower() == "nan":
                customer = ""

        rows_to_process.append({
            "excel_row": row_idx,
            "url":       urls[0],
            "customer":  customer,
        })

    total = len(rows_to_process)
    _cb(progress_cb, 0, total, f"Encontradas {total} linhas com links para processar")

    # ── Process each row ──────────────────────────────────────────────────────
    # raw_results: list of {customer, instance, count}
    raw_results: list[dict] = []

    for i, item in enumerate(rows_to_process):
        url      = item["url"]
        customer = item["customer"]
        _cb(progress_cb, i, total, f"Processando Linha {item['excel_row'] + 1}…")

        try:
            instances = fetch_estimate_instances(url)
            msg = f"  OK {len(instances)} tipo(s) encontrado(s)"
        except Exception as exc:
            instances = {}
            msg = f"  ERRO: {exc}"

        _cb(progress_cb, i, total, msg)

        for inst_type, count in instances.items():
            raw_results.append({
                "customer": customer,
                "instance": inst_type,
                "count":    count,
            })

        _cb(progress_cb, i + 1, total)

    # ── Summarize & build output ───────────────────────────────────────────────
    # Column order: #, Provider, Instance, Quantity, Company, Processor
    add_processor = cloud_provider.upper() == "AWS"

    # ── XPA: un grupo (DataFrame) por empresa ─────────────────────────────────
    if summarize_by == "xpa":
        return build_xpa_groups(raw_results, cloud_provider)

    if not raw_results:
        cols = ["#", "Provider", "Instance", "Quantity", "Company"]
        if summarize_by != "company":
            cols = ["#", "Provider", "Instance", "Quantity"]
        if add_processor:
            cols.append("Processor")
        return pd.DataFrame(columns=cols)

    output_rows: list[dict] = []
    counter = 1

    if summarize_by == "company":
        agg: dict[tuple, int] = defaultdict(int)
        for r in raw_results:
            agg[(r["customer"], r["instance"])] += r["count"]
        for (company, inst), cnt in sorted(agg.items()):
            row = {
                "#":        counter,
                "Provider": cloud_provider,
                "Instance": inst,
                "Quantity": cnt,
                "Company":  company,
            }
            if add_processor:
                row["Processor"] = classify_processor(inst)
            output_rows.append(row)
            counter += 1

    elif summarize_by == "total":
        agg_total: dict[str, int] = defaultdict(int)
        for r in raw_results:
            agg_total[r["instance"]] += r["count"]
        for inst, cnt in sorted(agg_total.items()):
            row = {
                "#":        counter,
                "Provider": cloud_provider,
                "Instance": inst,
                "Quantity": cnt,
            }
            if add_processor:
                row["Processor"] = classify_processor(inst)
            output_rows.append(row)
            counter += 1

    else:   # "none" – one row per raw result (no aggregation)
        for r in raw_results:
            row = {
                "#":        counter,
                "Provider": cloud_provider,
                "Instance": r["instance"],
                "Quantity": r["count"],
            }
            if add_processor:
                row["Processor"] = classify_processor(r["instance"])
            output_rows.append(row)
            counter += 1

    return pd.DataFrame(output_rows)


def _cb(fn, current, total, msg=""):
    if fn:
        fn(current, total, msg)
