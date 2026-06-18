import app as flask_app


def test_index_has_xpa_radio_and_no_grand_total():
    flask_app.app.config["TESTING"] = True
    client = flask_app.app.test_client()
    html = client.get("/").get_data(as_text=True)
    assert 'value="xpa"' in html
    assert 'value="total"' not in html
    assert 'value="company"' in html
    assert 'value="none"' in html
