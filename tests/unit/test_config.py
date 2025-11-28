"""
Unit tests for config.py module
"""
import os
import secrets
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from scaipot.utils.config import (
    _get_allowed_origins,
    _get_database_pool_size,
    _get_jwt_secret,
    _validate_production_config,
    load_config,
    validate_config,
)


class TestLoadConfig:
    """Test load_config function"""

    def test_load_config_with_env_file(self, tmp_path, test_config, clean_environment):
        """Test loading config with .env file present"""
        # Create a temporary .env file
        env_file = tmp_path / ".env"
        env_content = "\n".join([f"{k}={v}" for k, v in test_config.items()])
        env_file.write_text(env_content)

        # Change to directory with .env file
        with patch("os.chdir", lambda x: None):
            with patch("src.scaipot.utils.config.Path") as mock_path:
                mock_path.return_value.exists.return_value = True
                mock_path.return_value.__str__ = lambda self: str(env_file)

                with patch("dotenv.load_dotenv") as mock_load_dotenv:
                    with patch.dict(os.environ, test_config, clear=True):
                        config = load_config()

                        # Verify dotenv was called
                        mock_load_dotenv.assert_called_once()

                        # Verify config values are loaded
                        assert config["ANTHROPIC_API_KEY"] == test_config["ANTHROPIC_API_KEY"]
                        assert config["TELEGRAM_BOT_TOKEN"] == test_config["TELEGRAM_BOT_TOKEN"]

    def test_load_config_without_env_file(self, test_config, clean_environment):
        """Test loading config without .env file"""
        with patch("src.scaipot.utils.config.Path") as mock_path:
            mock_path.return_value.exists.return_value = False

            with patch.dict(os.environ, test_config, clear=True):
                config = load_config()

                # Verify config values are loaded from environment
                assert config["ANTHROPIC_API_KEY"] == test_config["ANTHROPIC_API_KEY"]
                assert config["ENV"] == "test"

    def test_load_config_all_fields(self, test_config, clean_environment):
        """Test that all expected config fields are present"""
        with patch("src.scaipot.utils.config.Path") as mock_path:
            mock_path.return_value.exists.return_value = False

            with patch.dict(os.environ, test_config, clear=True):
                config = load_config()

                # Check that all expected fields are present
                expected_fields = [
                    "TELEGRAM_BOT_TOKEN", "SIGNAL_PHONE_NUMBER", "ANTHROPIC_API_KEY",
                    "MCP_PROMPTS_URL", "DATABASE_URL", "REDIS_URL", "JWT_SECRET",
                    "ALLOWED_ORIGINS", "LOG_LEVEL", "ENV", "DEBUG"
                ]

                for field in expected_fields:
                    assert field in config, f"Missing config field: {field}"

    def test_load_config_calls_validation(self, test_config, clean_environment):
        """Test that production config validation is called"""
        with patch("src.scaipot.utils.config.Path") as mock_path:
            mock_path.return_value.exists.return_value = False

            with patch.dict(os.environ, test_config, clear=True):
                with patch("src.scaipot.utils.config._validate_production_config") as mock_validate:
                    load_config()
                    mock_validate.assert_called_once()


class TestGetDatabasePoolSize:
    """Test _get_database_pool_size function"""

    def test_get_database_pool_size_valid_range(self, clean_environment):
        """Test valid pool size values"""
        test_cases = [1, 10, 50, 100]

        for size in test_cases:
            with patch.dict(os.environ, {"DATABASE_POOL_SIZE": str(size)}, clear=True):
                result = _get_database_pool_size()
                assert result == size

    def test_get_database_pool_size_invalid_values(self, clean_environment):
        """Test invalid pool size values fall back to default"""
        invalid_cases = ["0", "101", "-1", "abc", ""]

        for invalid_value in invalid_cases:
            with patch.dict(os.environ, {"DATABASE_POOL_SIZE": invalid_value}, clear=True):
                with patch("src.scaipot.utils.config.logger") as mock_logger:
                    result = _get_database_pool_size()
                    assert result == 20  # Default value
                    mock_logger.warning.assert_called()

    def test_get_database_pool_size_no_env(self, clean_environment):
        """Test default value when env var not set"""
        result = _get_database_pool_size()
        assert result == 20

    def test_get_database_pool_size_boundary_values(self, clean_environment):
        """Test boundary values"""
        # Test minimum
        with patch.dict(os.environ, {"DATABASE_POOL_SIZE": "1"}, clear=True):
            assert _get_database_pool_size() == 1

        # Test maximum
        with patch.dict(os.environ, {"DATABASE_POOL_SIZE": "100"}, clear=True):
            assert _get_database_pool_size() == 100


class TestGetJwtSecret:
    """Test _get_jwt_secret function"""

    def test_get_jwt_secret_custom_value(self, clean_environment):
        """Test custom JWT secret"""
        custom_secret = "my_custom_secret_12345"
        with patch.dict(os.environ, {"JWT_SECRET": custom_secret}, clear=True):
            result = _get_jwt_secret()
            assert result == custom_secret

    def test_get_jwt_secret_development_auto_generate(self, clean_environment):
        """Test auto-generation in development environment"""
        with patch.dict(os.environ, {"ENV": "development"}, clear=True):
            with patch("src.scaipot.utils.config.logger") as mock_logger:
                result = _get_jwt_secret()

                # Should generate a random secret
                assert isinstance(result, str)
                assert len(result) > 32  # secrets.token_urlsafe(32) is longer than 32

                mock_logger.info.assert_called_with(
                    "Generating random JWT_SECRET for development environment"
                )

    def test_get_jwt_secret_production_requires_secret(self, clean_environment):
        """Test that production requires explicit JWT secret"""
        with patch.dict(os.environ, {"ENV": "production"}, clear=True):
            with pytest.raises(ValueError, match="JWT_SECRET must be set"):
                _get_jwt_secret()

    def test_get_jwt_secret_production_with_secret(self, clean_environment):
        """Test production with valid secret"""
        custom_secret = "prod_secret_123"
        with patch.dict(os.environ, {
            "ENV": "production",
            "JWT_SECRET": custom_secret
        }, clear=True):
            result = _get_jwt_secret()
            assert result == custom_secret

    def test_get_jwt_secret_empty_in_production(self, clean_environment):
        """Test empty JWT secret in production"""
        with patch.dict(os.environ, {"ENV": "production", "JWT_SECRET": ""}, clear=True):
            with pytest.raises(ValueError, match="JWT_SECRET must be set"):
                _get_jwt_secret()


class TestGetAllowedOrigins:
    """Test _get_allowed_origins function"""

    def test_get_allowed_origins_single_value(self, clean_environment):
        """Test single origin value"""
        with patch.dict(os.environ, {"ALLOWED_ORIGINS": "http://localhost:3001"}, clear=True):
            result = _get_allowed_origins()
            assert result == ["http://localhost:3001"]

    def test_get_allowed_origins_multiple_values(self, clean_environment):
        """Test multiple origin values"""
        origins_str = "http://localhost:3001,https://example.com,http://test.com"
        with patch.dict(os.environ, {"ALLOWED_ORIGINS": origins_str}, clear=True):
            result = _get_allowed_origins()
            expected = ["http://localhost:3001", "https://example.com", "http://test.com"]
            assert result == expected

    def test_get_allowed_origins_with_spaces(self, clean_environment):
        """Test origins with extra spaces"""
        origins_str = " http://localhost:3001 , https://example.com "
        with patch.dict(os.environ, {"ALLOWED_ORIGINS": origins_str}, clear=True):
            result = _get_allowed_origins()
            expected = ["http://localhost:3001", "https://example.com"]
            assert result == expected

    def test_get_allowed_origins_empty_values_filtered(self, clean_environment):
        """Test that empty values are filtered out"""
        origins_str = "http://localhost:3001,,https://example.com,"
        with patch.dict(os.environ, {"ALLOWED_ORIGINS": origins_str}, clear=True):
            result = _get_allowed_origins()
            expected = ["http://localhost:3001", "https://example.com"]
            assert result == expected

    def test_get_allowed_origins_no_env_default(self, clean_environment):
        """Test default value when env var not set"""
        with patch("src.scaipot.utils.config.logger") as mock_logger:
            result = _get_allowed_origins()
            assert result == ["http://localhost:3001"]
            mock_logger.warning.assert_called_with(
                "No ALLOWED_ORIGINS configured, using default localhost:3001"
            )


class TestValidateProductionConfig:
    """Test _validate_production_config function"""

    def test_validate_production_config_development_skip(self, clean_environment):
        """Test that validation is skipped in development"""
        config = {"ENV": "development"}
        _validate_production_config(config)  # Should not raise

    def test_validate_production_config_missing_anthropic_key(self, clean_environment):
        """Test production validation requires Anthropic API key"""
        config = {
            "ENV": "production",
            "DATABASE_URL": "postgresql://test:test@localhost/test",
        }

        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY is required for production"):
            _validate_production_config(config)

    def test_validate_production_config_weak_database_password(self, clean_environment):
        """Test production validation rejects weak database password"""
        config = {
            "ENV": "production",
            "ANTHROPIC_API_KEY": "test_key",
            "DATABASE_URL": "postgresql://scaipot:password@localhost/test",
        }

        with pytest.raises(ValueError, match="contains default password"):
            _validate_production_config(config)

    def test_validate_production_config_valid_config(self, clean_environment):
        """Test valid production config passes validation"""
        config = {
            "ENV": "production",
            "ANTHROPIC_API_KEY": "test_key_123",
            "DATABASE_URL": "postgresql://scaipot:strong_password_123@localhost/test",
            "HONEYPOT_VM_ENABLED": False,
        }

        with patch("src.scaipot.utils.config.logger") as mock_logger:
            _validate_production_config(config)
            mock_logger.info.assert_called_with("Production security validation passed")

    def test_validate_production_config_vm_warning(self, clean_environment):
        """Test VM enabled warning in production"""
        config = {
            "ENV": "production",
            "ANTHROPIC_API_KEY": "test_key_123",
            "DATABASE_URL": "postgresql://scaipot:strong_password_123@localhost/test",
            "HONEYPOT_VM_ENABLED": True,
        }

        with patch("src.scaipot.utils.config.logger") as mock_logger:
            _validate_production_config(config)
            mock_logger.warning.assert_called_with(
                "HONEYPOT_VM_ENABLED is active in production. "
                "Ensure Docker socket is protected via docker-socket-proxy."
            )


class TestValidateConfig:
    """Test validate_config function"""

    def test_validate_config_all_required_fields(self, test_config, clean_environment):
        """Test config with all required fields"""
        result = validate_config(test_config)
        assert result is True

    def test_validate_config_missing_required_fields(self, clean_environment):
        """Test config missing required fields"""
        incomplete_config = {
            "TELEGRAM_BOT_TOKEN": "test_token",
            # Missing ANTHROPIC_API_KEY, DATABASE_URL, REDIS_URL
        }

        with pytest.raises(ValueError, match="Missing required configuration"):
            validate_config(incomplete_config)

    def test_validate_config_empty_required_fields(self, clean_environment):
        """Test config with empty required fields"""
        config_with_empty = {
            "ANTHROPIC_API_KEY": "",
            "DATABASE_URL": "postgresql://test",
            "REDIS_URL": "",
        }

        with pytest.raises(ValueError, match="Missing required configuration"):
            validate_config(config_with_empty)

    @pytest.mark.parametrize("missing_field", [
        "ANTHROPIC_API_KEY",
        "DATABASE_URL",
        "REDIS_URL"
    ])
    def test_validate_config_individual_missing_fields(self, test_config, missing_field, clean_environment):
        """Test config missing individual required fields"""
        config = test_config.copy()
        del config[missing_field]

        with pytest.raises(ValueError, match=f"Missing required configuration.*{missing_field}"):
            validate_config(config)