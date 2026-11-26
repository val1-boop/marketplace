def test_privacy_page_requires_login_and_lists_protections(client, as_alice):
    page = as_alice.get("/profile/privacy").get_data(as_text=True)
    assert "Privacidad de cuenta" in page and "30 minutos" in page


def test_privacy_page_redirects_anonymous_to_login(client):
    response = client.get("/profile/privacy")
    assert response.status_code == 302 and "/auth/login" in response.headers["Location"]
