"""Run the bundled page script in an isolated JS VM, with fake player payloads."""
import json
import shutil
import subprocess
import pytest
from pluma.youtube import DATA_SCRIPT, source


def evaluate(expression, host='www.youtube.com', allowed=()):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node required for isolated script tests')
    setup = """
        const vm=require('node:vm');
        const sandbox=vm.createContext({URL});
        vm.runInContext("globalThis.window=globalThis;globalThis.location={hostname:"+HOST+"};",sandbox);
    """.replace('HOST', json.dumps(json.dumps(host)))
    setup += 'vm.runInContext("globalThis.Response=class {constructor(url,data){this.url=url;this.data=data;}json(){return Promise.resolve(this.data);}};",sandbox);'
    program = setup + '\nvm.runInContext(' + json.dumps(source(DATA_SCRIPT, allowed)) + ',sandbox);\n'
    program += 'Promise.resolve(vm.runInContext(' + json.dumps(expression) + ',sandbox)).then(value=>console.log(JSON.stringify(value)));'
    completed = subprocess.run([node, '-e', program], capture_output=True, text=True, check=True, timeout=10)
    return json.loads(completed.stdout)


def test_player_payload_is_pruned_without_touching_video():
    value = evaluate("""JSON.parse('{"videoDetails":{"videoId":"real"},"streamingData":{"url":"keep"},"playerAds":[1],"adPlacements":[2],"adSlots":[3]}')""")
    assert value == {'videoDetails': {'videoId': 'real'}, 'streamingData': {'url': 'keep'}}


def test_initial_player_and_nested_playlist_data():
    value = evaluate("""(()=>{
        window.ytInitialPlayerResponse={videoDetails:{videoId:'keep'},adSlots:[1]};
        const next=JSON.parse('{"playerResponse":{"playerAds":[1],"videoDetails":{"videoId":"next"}}}');
        return {initial:window.ytInitialPlayerResponse,next};
    })()""")
    assert value['initial'] == {'videoDetails': {'videoId': 'keep'}}
    assert value['next']['playerResponse'] == {'videoDetails': {'videoId': 'next'}}


def test_unrelated_json_and_reviver_are_unchanged():
    assert evaluate("""JSON.parse('{"count":2,"adSlots":["not a player"]}',(key,v)=>key==='count'?v+1:v)""") == {
        'count': 3, 'adSlots': ['not a player']}


@pytest.mark.parametrize('host,allowed', [
    ('notyoutube.com', ()), ('youtube.com.evil.org', ()), ('www.youtube.com', ('youtube.com',)),
])
def test_host_scope_and_site_exception(host, allowed):
    assert 'playerAds' in evaluate("""JSON.parse('{"videoDetails":{},"playerAds":[1]}')""", host, allowed)


def test_fetch_player_response_and_unrelated_endpoint():
    value = evaluate("""Promise.all([
        new Response('https://www.youtube.com/youtubei/v1/player',{adSlots:[1],streamingData:{keep:true}}).json(),
        new Response('https://example.org/api',{adSlots:[1],streamingData:{keep:true}}).json()
    ])""")
    assert value[0] == {'streamingData': {'keep': True}}
    assert value[1]['adSlots'] == [1]
