from duck_jenkins._utils import upstream_lookup


def test_upstream_lookup():
    file_name = f'./data/pipeline1_build_3.json'
    c = upstream_lookup(file_name)
    assert c['upstreamProject'] == 'pipeline2/master'
    assert c['upstreamBuild'] == 2
