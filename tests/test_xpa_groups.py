from excel_processor import build_xpa_groups


def test_groups_by_company_and_aggregates():
    raw = [
        {"customer": "Esfera", "instance": "m7i.large", "count": 2},
        {"customer": "Esfera", "instance": "m7i.large", "count": 3},
        {"customer": "Esfera", "instance": "c7g.xlarge", "count": 1},
        {"customer": "UOL", "instance": "t3.medium", "count": 4},
    ]
    groups = build_xpa_groups(raw, "AWS")

    assert set(groups.keys()) == {"Esfera", "UOL"}

    esfera = groups["Esfera"]
    assert list(esfera.columns) == ["#", "Provider", "Instance", "Quantity"]
    # instancias en orden alfabético, # desde 1, cantidades sumadas
    assert esfera["#"].tolist() == [1, 2]
    assert esfera["Instance"].tolist() == ["c7g.xlarge", "m7i.large"]
    assert esfera["Quantity"].tolist() == [1, 5]
    assert esfera["Provider"].tolist() == ["AWS", "AWS"]

    uol = groups["UOL"]
    assert uol["#"].tolist() == [1]
    assert uol["Quantity"].tolist() == [4]


def test_blank_company_goes_to_sinempresa():
    raw = [{"customer": "", "instance": "t3.large", "count": 1}]
    groups = build_xpa_groups(raw, "AWS")
    assert list(groups.keys()) == ["SinEmpresa"]


def test_empty_input_returns_empty_dict():
    assert build_xpa_groups([], "AWS") == {}
