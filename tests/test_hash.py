from data_gatherer.util.hash import sha256_of_manifest, canonical_json

def test_hash_stable_key_order():
    a = {'b': 1, 'a': 2}
    b = {'a': 2, 'b': 1}
    assert canonical_json(a) == canonical_json(b)
    assert sha256_of_manifest(a) == sha256_of_manifest(b)
