from app.main import health_check

def test_health_check_endpoint():
    """Valida o endpoint de health check para monitoramento de contêineres Docker/Kubernetes."""
    data = health_check()
    assert data["status"] == "healthy"
    assert "UrbanVision" in data["app"]
    assert "database" in data
