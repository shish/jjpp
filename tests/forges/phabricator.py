import logging

from jjpr.forges import phabricator

log = logging.getLogger(__name__)


class TestPhabricatorClient:
    def test_flatten_params(self):
        params = {
            "key1": "value1",
            "key2": {
                "subkey1": "subvalue1",
                "subkey2": ["listitem1", "listitem2"],
            },
            "key3": ["listitem3", {"subkey3": "subvalue3"}],
        }
        formed_params = {}
        phabricator.PhabricatorClient._struct2http(
            base=None, formed_params=formed_params, params=params
        )
        expected = {
            "key1": "value1",
            "key2[subkey1]": "subvalue1",
            "key2[subkey2][0]": "listitem1",
            "key2[subkey2][1]": "listitem2",
            "key3[0]": "listitem3",
            "key3[1][subkey3]": "subvalue3",
        }
        assert formed_params == expected
