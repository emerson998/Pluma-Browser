"""Bundled, host-scoped YouTube protection. No downloaded executable scriptlets."""
import json

DATA_SCRIPT = r"""
(()=>{
    const host=location.hostname.toLowerCase();
    const hosts=['www.youtube.com','m.youtube.com','music.youtube.com','youtube.com',
                 'www.youtube-nocookie.com','youtube-nocookie.com'];
    if(!hosts.includes(host))return;
    const allowed=__ALLOWED__;
    if(allowed.some(d=>host===d||host.endsWith('.'+d)))return;
    const parse=JSON.parse, stringify=JSON.stringify;
    function clean(value, force=false, depth=0){
        if(!value||typeof value!=='object'||depth>3)return value;
        if(Array.isArray(value)){
            for(const entry of value.slice(0,100))clean(entry,false,depth+1);
            return value;
        }
        if(force||value.playabilityStatus||value.videoDetails||value.streamingData){
            for(const key of ['adPlacements','playerAds','adSlots'])
                if(Object.prototype.hasOwnProperty.call(value,key))delete value[key];
        }
        if(value.playerResponse)clean(value.playerResponse,true,depth+1);
        if(value.response)clean(value.response,false,depth+1);
        if(typeof value.player_response==='string'&&value.player_response.length<2000000){
            try{value.player_response=stringify(clean(parse(value.player_response),true,depth+1));}catch{}
        }
        return value;
    }
    JSON.parse=function(...args){return clean(Reflect.apply(parse,this,args));};
    const descriptor=Object.getOwnPropertyDescriptor(window,'ytInitialPlayerResponse');
    if(!descriptor||descriptor.configurable){
        let initial=descriptor&&descriptor.value;
        try{
            Object.defineProperty(window,'ytInitialPlayerResponse',{
                configurable:true,enumerable:true,
                get(){return initial;},set(value){initial=clean(value,true);}
            });
            if(initial)initial=clean(initial,true);
        }catch{}
    }
    if(typeof Response!=='undefined'){
        const original=Response.prototype.json;
        Response.prototype.json=function(...args){
            const promise=Reflect.apply(original,this,args);
            let player=false;
            try{
                const url=new URL(this.url);
                player=hosts.includes(url.hostname)&&/^\/youtubei\/v1\/(player|next|reel\/reel_item_watch)/.test(url.pathname);
            }catch{}
            return player?promise.then(value=>clean(value,true)):promise;
        };
    }
})()
"""

DOM_SCRIPT = r"""
(()=>{
    const host=location.hostname.toLowerCase();
    if(!['www.youtube.com','m.youtube.com','music.youtube.com','youtube.com',
         'www.youtube-nocookie.com','youtube-nocookie.com'].includes(host))return;
    const allowed=__ALLOWED__;
    if(allowed.some(d=>host===d||host.endsWith('.'+d)))return;
    const style=document.createElement('style');
    style.textContent='ytd-ad-slot-renderer,ytd-display-ad-renderer,ytd-promoted-sparkles-web-renderer,'+
        'ytd-promoted-video-renderer,ytd-in-feed-ad-layout-renderer,.ytp-ad-overlay-container{display:none!important}';
    document.documentElement.append(style);
    let player=null, classes=null, buttons=null, waiting=null, scheduled=false;
    function skip(){
        scheduled=false;
        if(!player||!player.isConnected)return;
        const ad=player.classList.contains('ad-showing')||player.classList.contains('ad-interrupting');
        if(!ad){if(buttons){buttons.disconnect();buttons=null;}return;}
        if(!buttons){
            buttons=new MutationObserver(schedule);
            buttons.observe(player,{childList:true,subtree:true});
        }
        const button=player.querySelector('.ytp-skip-ad-button,.ytp-ad-skip-button,.ytp-ad-skip-button-modern,.ytp-ad-skip-button-slot button');
        if(button&&!button.disabled&&button.getBoundingClientRect().width>0)button.click();
    }
    function schedule(){
        if(!scheduled){scheduled=true;requestAnimationFrame(skip);}
    }
    function attach(){
        const next=document.querySelector('#movie_player,.html5-video-player');
        if(next===player&&player&&player.isConnected)return;
        if(classes)classes.disconnect();
        if(buttons){buttons.disconnect();buttons=null;}
        player=next;
        if(player){
            if(waiting){waiting.disconnect();waiting=null;}
            classes=new MutationObserver(schedule);
            classes.observe(player,{attributes:true,attributeFilter:['class']});
            schedule();
        }else if(!/^\/(watch|shorts|embed|live)(\/|$)/.test(location.pathname)){
            if(waiting){waiting.disconnect();waiting=null;}
        }else if(!waiting){
            waiting=new MutationObserver(()=>{
                if(document.querySelector('#movie_player,.html5-video-player'))attach();
            });
            waiting.observe(document.documentElement,{childList:true,subtree:true});
        }
    }
    document.addEventListener('yt-navigate-finish',attach);
    window.addEventListener('pageshow',attach);
    document.addEventListener('loadedmetadata',attach,true);
    window.addEventListener('pagehide',()=>{
        if(classes)classes.disconnect();
        if(buttons)buttons.disconnect();
        if(waiting)waiting.disconnect();
        classes=null;buttons=null;waiting=null;player=null;scheduled=false;
    });
    attach();
})()
"""


def source(text, allowed=()):
    return text.replace('__ALLOWED__', json.dumps(sorted(allowed)))


def install(profile, allowed=(), enabled=True):
    from PySide6.QtWebEngineCore import QWebEngineScript
    collection = profile.scripts()
    for name in ('Pluma YouTube data', 'Pluma YouTube player'):
        for old in collection.find(name):
            collection.remove(old)
    if not enabled:
        return
    for name, text, point, world in (
        ('Pluma YouTube data', DATA_SCRIPT, QWebEngineScript.InjectionPoint.DocumentCreation,
         QWebEngineScript.ScriptWorldId.MainWorld),
        ('Pluma YouTube player', DOM_SCRIPT, QWebEngineScript.InjectionPoint.DocumentReady,
         QWebEngineScript.ScriptWorldId.ApplicationWorld),
    ):
        script = QWebEngineScript()
        script.setName(name)
        script.setInjectionPoint(point)
        script.setWorldId(world.value)
        script.setRunsOnSubFrames(True)
        script.setSourceCode(source(text, allowed))
        collection.insert(script)
