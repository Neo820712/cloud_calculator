from datetime import date

from excel_processor import month_name_es, safe_company_filename, xpa_filename


def test_month_name_es_returns_lowercase_spanish():
    assert month_name_es(date(2026, 6, 18)) == "junio"
    assert month_name_es(date(2026, 1, 1)) == "enero"
    assert month_name_es(date(2026, 12, 31)) == "diciembre"


def test_safe_company_filename_replaces_invalid_chars():
    # 8 invalid chars: \ / : * ? " < > |
    assert safe_company_filename('A/B:C*?"<>|D\\E') == "A_B_C______D_E"


def test_safe_company_filename_blank_becomes_sinempresa():
    assert safe_company_filename("") == "SinEmpresa"
    assert safe_company_filename("   ") == "SinEmpresa"
    assert safe_company_filename("///") == "SinEmpresa"


def test_xpa_filename_format():
    assert xpa_filename("Esfera", date(2026, 6, 18)) == "Esfera_2026_junio.xlsx"
    assert xpa_filename("", date(2026, 6, 18)) == "SinEmpresa_2026_junio.xlsx"
