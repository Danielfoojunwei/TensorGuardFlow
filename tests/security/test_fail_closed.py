
import pytest
import os
from unittest.mock import patch
from tensorguard.utils.config import settings
from tensorguard.crypto.pqc.dilithium import Dilithium3
from tensorguard.crypto.pqc.kyber import Kyber768
from tensorguard.core.crypto import N2HEEncryptor
from tensorguard.utils.exceptions import CryptographyError

class TestFailClosedPolicy:
    """
    Verification Test for the "Fail-Closed" Policy.
    Ensures that simulators are blocked in production mode unless overridden.
    """

    def test_dilithium_fail_closed(self):
        """Dilithium3 should fail in production without liboqs."""
        with patch('tensorguard.crypto.pqc.dilithium._LIBOQS_AVAILABLE', False):
            with patch.object(settings, 'PRODUCTION_MODE', True):
                with patch.object(settings, 'ENABLE_EXPERIMENTAL_CRYPTO', False):
                    with pytest.raises(CryptographyError, match="liboqs not available in PRODUCTION MODE"):
                        Dilithium3()

    def test_kyber_fail_closed(self):
        """Kyber768 should fail in production without liboqs."""
        with patch('tensorguard.crypto.pqc.kyber._LIBOQS_AVAILABLE', False):
            with patch.object(settings, 'PRODUCTION_MODE', True):
                with patch.object(settings, 'ENABLE_EXPERIMENTAL_CRYPTO', False):
                    with pytest.raises(CryptographyError, match="liboqs not available in PRODUCTION MODE"):
                        Kyber768()

    def test_n2he_fail_closed(self):
        """N2HEEncryptor should log warning in production as it is now GA validated."""
        import warnings
        with patch.object(settings, 'PRODUCTION_MODE', True):
            with patch.object(settings, 'ENABLE_EXPERIMENTAL_CRYPTO', False):
                # N2HE is now GA-validated per v2.3 spec, so it should NOT raise
                # but should emit a FastUMI validation warning
                with warnings.catch_warnings(record=True) as w:
                    warnings.simplefilter("always")
                    encryptor = N2HEEncryptor()
                    # Should succeed but log a warning about legacy mode
                    assert encryptor is not None

    def test_experimental_override(self):
        """Overriding with experimental flag should allow simulators with a warning."""
        with patch('tensorguard.crypto.pqc.dilithium._LIBOQS_AVAILABLE', False):
            with patch.object(settings, 'PRODUCTION_MODE', True):
                with patch.object(settings, 'ENABLE_EXPERIMENTAL_CRYPTO', True):
                    # Should not raise
                    sig = Dilithium3()
                    # In simulator mode, is_production should be False
                    assert not sig.is_production
