import io

import pandas as pd

import excel_processor


def _make_excel_bytes():
    # header en fila 1 (header_row=1). Col A = Customer (E? usamos posiciones simples).
    # Construimos columnas hasta 'J' para el link. Customer en col A, link en col B.
    df = pd.DataFrame({
        "Customer": ["Esfera", "UOL"],
        "Link": [
            "https://calculator.aws/#/estimate?id=AAA",
            "https://calculator.aws/#/estimate?id=BBB",
        ],
    })
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False)
    buf.seek(0)
    return buf.getvalue()


def test_process_excel_file_xpa_returns_dict_of_groups(monkeypatch):
    fake = {
        "AAA": {"m7i.large": 2},
        "BBB": {"t3.medium": 5},
    }

    def fake_fetch(url):
        if "AAA" in url:
            return fake["AAA"]
        return fake["BBB"]

    monkeypatch.setattr(excel_processor, "fetch_estimate_instances", fake_fetch)

    result = excel_processor.process_excel_file(
        _make_excel_bytes(),
        link_column="B",
        header_row=1,
        cloud_provider="AWS",
        customer_column="A",
        summarize_by="xpa",
    )

    assert isinstance(result, dict)
    assert set(result.keys()) == {"Esfera", "UOL"}
    esfera = result["Esfera"]
    assert list(esfera.columns) == ["#", "Provider", "Instance", "Quantity"]
    assert esfera["Instance"].tolist() == ["m7i.large"]
    assert esfera["Quantity"].tolist() == [2]


def test_process_excel_file_xpa_empty_returns_empty_dict(monkeypatch):
    monkeypatch.setattr(excel_processor, "fetch_estimate_instances", lambda url: {})
    result = excel_processor.process_excel_file(
        _make_excel_bytes(),
        link_column="B",
        header_row=1,
        cloud_provider="AWS",
        customer_column="A",
        summarize_by="xpa",
    )
    assert result == {}
