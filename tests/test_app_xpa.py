import io
import time
import zipfile

import pandas as pd

import app as flask_app


def _client():
    flask_app.app.config["TESTING"] = True
    return flask_app.app.test_client()


def _wait_done(client, job_id, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/status/{job_id}")
        data = r.get_json()
        if data["status"] in ("done", "error"):
            return data
        time.sleep(0.05)
    raise AssertionError("job no terminó a tiempo")


def test_xpa_requires_customer_column():
    client = _client()
    data = {
        "summarize_by": "xpa",
        "customer_column": "",
        "link_column": "B",
        "header_row": "1",
        "cloud_provider": "AWS",
    }
    data["excel_file"] = (io.BytesIO(b"dummy"), "in.xlsx")
    r = client.post("/process", data=data, content_type="multipart/form-data")
    assert r.status_code == 400
    assert "Customer" in r.get_json()["error"]


def test_xpa_download_returns_zip(monkeypatch):
    groups = {
        "Esfera": pd.DataFrame(
            [{"#": 1, "Provider": "AWS", "Instance": "m7i.large", "Quantity": 2}],
            columns=["#", "Provider", "Instance", "Quantity"],
        ),
        "UOL": pd.DataFrame(
            [{"#": 1, "Provider": "AWS", "Instance": "t3.medium", "Quantity": 5}],
            columns=["#", "Provider", "Instance", "Quantity"],
        ),
    }
    monkeypatch.setattr(flask_app, "process_excel_file", lambda *a, **k: groups)

    client = _client()
    data = {
        "summarize_by": "xpa",
        "customer_column": "A",
        "link_column": "B",
        "header_row": "1",
        "cloud_provider": "AWS",
    }
    data["excel_file"] = (io.BytesIO(b"dummy"), "in.xlsx")
    r = client.post("/process", data=data, content_type="multipart/form-data")
    assert r.status_code == 200
    job_id = r.get_json()["job_id"]

    status = _wait_done(client, job_id)
    assert status["status"] == "done", status

    dl = client.get(f"/download/{job_id}")
    assert dl.status_code == 200
    assert dl.mimetype == "application/zip"

    zf = zipfile.ZipFile(io.BytesIO(dl.data))
    names = sorted(zf.namelist())
    assert len(names) == 2
    assert any(n.startswith("Esfera_") and n.endswith(".xlsx") for n in names)
    assert any(n.startswith("UOL_") and n.endswith(".xlsx") for n in names)

    # cada archivo NO tiene fila de encabezado: la primera celda es el "#" = 1
    first = [n for n in names if n.startswith("Esfera_")][0]
    df = pd.read_excel(io.BytesIO(zf.read(first)), header=None)
    assert df.iloc[0, 0] == 1
    assert df.iloc[0, 1] == "AWS"
    assert df.shape[1] == 4


def test_non_xpa_still_returns_xlsx(monkeypatch):
    df = pd.DataFrame(
        [{"#": 1, "Provider": "AWS", "Instance": "t3.large", "Quantity": 1, "Company": "X"}]
    )
    monkeypatch.setattr(flask_app, "process_excel_file", lambda *a, **k: df)

    client = _client()
    data = {
        "summarize_by": "company",
        "customer_column": "A",
        "link_column": "B",
        "header_row": "1",
        "cloud_provider": "AWS",
    }
    data["excel_file"] = (io.BytesIO(b"dummy"), "in.xlsx")
    r = client.post("/process", data=data, content_type="multipart/form-data")
    job_id = r.get_json()["job_id"]
    _wait_done(client, job_id)

    dl = client.get(f"/download/{job_id}")
    assert dl.status_code == 200
    assert "spreadsheetml" in dl.mimetype
