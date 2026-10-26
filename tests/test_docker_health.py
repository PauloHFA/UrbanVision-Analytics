from app.main import health_check

def test_health_check_endpoint():
    """Valida o endpoint de health check para monitoramento de contêineres Docker/Kubernetes."""
    data = health_check()
    assert data["status"] == "healthy"
    assert "UrbanVision" in data["app"]
    assert "database" in data



def test_dashboard_page_rendering():
    """Valida renderização da interface web do dashboard (HTTP 200)."""
    from starlette.requests import Request
    from app.main import dashboard

    scope = {"type": "http", "method": "GET", "path": "/", "headers": []}
    req = Request(scope)
    resp = dashboard(req)
    assert resp.status_code == 200
    assert b"UrbanVision" in resp.body
