from app.auth.rate_limit import login_bucket_key


def test_login_bucket_does_not_expose_email_or_client_identifier() -> None:
    email = "Employee.Engineering@example.com"
    client_identifier = "192.0.2.10"

    key = login_bucket_key(email=email, client_identifier=client_identifier)

    assert key.startswith("auth:login:")
    assert email.casefold() not in key
    assert client_identifier not in key
