import pytest

from app.collectors.url_policy import UnsafeUrlError, UrlPolicy


def public_resolver(_: str) -> list[str]:
    return ["93.184.216.34", "2606:2800:220:1:248:1893:25c8:1946"]


@pytest.mark.parametrize("scheme", ["http", "https"])
def test_public_allowed_urls(scheme: str) -> None:
    UrlPolicy(["example.com"], public_resolver).validate_before_navigation(
        f"{scheme}://example.com/product"
    )


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/p",
        "https:///missing-host",
        "https://user:pass@example.com/p",
        "https://other.example/p",
        "https://localhost/p",
        "https://foo.localhost/p",
    ],
)
def test_invalid_url_shapes(url: str) -> None:
    with pytest.raises(UnsafeUrlError):
        UrlPolicy(["example.com"], public_resolver).validate_before_navigation(url)


@pytest.mark.parametrize(
    "address",
    ["10.0.0.1", "127.0.0.1", "169.254.1.1", "::1", "fc00::1", "fe80::1"],
)
def test_literal_non_public_addresses_are_rejected(address: str) -> None:
    host = f"[{address}]" if ":" in address else address
    with pytest.raises(UnsafeUrlError):
        UrlPolicy([address], public_resolver).validate_before_navigation(f"https://{host}/")


def test_dns_resolution_to_private_address_is_rejected() -> None:
    with pytest.raises(UnsafeUrlError):
        UrlPolicy(["example.com"], lambda _: ["192.168.1.1"]).validate_before_navigation(
            "https://example.com/"
        )


def test_final_redirect_must_remain_allowed() -> None:
    with pytest.raises(UnsafeUrlError):
        UrlPolicy(["example.com"], public_resolver).validate_after_navigation(
            "https://attacker.example/"
        )
