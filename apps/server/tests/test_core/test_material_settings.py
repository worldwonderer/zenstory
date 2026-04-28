from __future__ import annotations

from config.material_settings import MaterialSettings


class TestMaterialSettings:
    def test_relationship_extraction_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv("MATERIAL_ENABLE_RELATIONSHIP_EXTRACTION", raising=False)

        settings = MaterialSettings(_env_file=None)

        assert settings.ENABLE_RELATIONSHIP_EXTRACTION is False

    def test_relationship_extraction_can_be_enabled_via_env(self, monkeypatch):
        monkeypatch.setenv("MATERIAL_ENABLE_RELATIONSHIP_EXTRACTION", "true")

        settings = MaterialSettings(_env_file=None)

        assert settings.ENABLE_RELATIONSHIP_EXTRACTION is True
