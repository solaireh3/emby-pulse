from fastapi import APIRouter, Response
from app.core.config import cfg
import requests
import urllib.parse
import logging

logger = logging.getLogger("uvicorn")
router = APIRouter()

smart_image_cache = {}

def get_real_image_id_robust(item_id: str):
    """智能 ID 转换（解决剧集封面变单集截图的问题）"""
    key = cfg.get("emby_api_key")
    host = cfg.get("emby_host")
    if not key or not host: return item_id

    params_base = {"api_key": key}

    try:
        url_a = f"{host}/emby/Items/{item_id}"
        res_a = requests.get(url_a, params={**params_base, "Fields": "SeriesId,ParentId"}, timeout=3)
        if res_a.status_code == 200:
            data = res_a.json()
            if data.get("SeriesId"): return data['SeriesId']
            if data.get("Type") == "Episode" and data.get("ParentId"): return data['ParentId']
    except: pass

    try:
        url_b = f"{host}/emby/Items/{item_id}/Ancestors"
        res_b = requests.get(url_b, params=params_base, timeout=3)
        if res_b.status_code == 200:
            for ancestor in res_b.json():
                if ancestor.get("Type") == "Series": return ancestor['Id']
                if ancestor.get("Type") == "Season" and not ancestor.get("SeriesId"): return ancestor['Id']
    except: pass

    try:
        url_c = f"{host}/emby/Items"
        res_c = requests.get(url_c, params={**params_base, "Ids": item_id, "Fields": "SeriesId", "Recursive": "true"}, timeout=3)
        if res_c.status_code == 200:
            items = res_c.json().get("Items", [])
            if items and items[0].get("SeriesId"): return items[0]['SeriesId']
    except: pass

    return item_id

@router.get("/api/proxy/image/{item_id}/{img_type}")
def proxy_image(item_id: str, img_type: str):
    key = cfg.get("emby_api_key"); host = cfg.get("emby_host")
    if not key or not host: return Response(status_code=404)
    try:
        target_id = get_real_image_id_robust(item_id) if img_type.lower() == 'primary' else item_id
        url = f"{host}/emby/Items/{target_id}/Images/{img_type}?maxHeight=600&maxWidth=400&quality=90&api_key={key}"
        resp = requests.get(url, timeout=10, stream=True)
        if resp.status_code == 200:
            return Response(content=resp.content, media_type=resp.headers.get("Content-Type", "image/jpeg"), headers={"Cache-Control": "no-cache"})
        
        if resp.status_code == 404 and target_id != item_id:
            fallback_url = f"{host}/emby/Items/{item_id}/Images/{img_type}?maxHeight=600&maxWidth=400&quality=90&api_key={key}"
            fallback_resp = requests.get(fallback_url, timeout=10, stream=True)
            if fallback_resp.status_code == 200:
                 return Response(content=fallback_resp.content, media_type=fallback_resp.headers.get("Content-Type", "image/jpeg"), headers={"Cache-Control": "no-cache"})
    except Exception: pass
    return Response(status_code=404)


@router.get("/api/proxy/smart_image")
def proxy_smart_image(item_id: str, name: str = "", year: str = "", type: str = "Primary"):
    """
    🔥 三级海报防裂兜底引擎：
    1. 查 Emby 原 ID
    2. 查 Emby 新 ID (洗版兜底)
    3. 查 TMDB 官方 (删库兜底)
    """
    key = cfg.get("emby_api_key")
    host = cfg.get("emby_host")
    if not key or not host: return Response(status_code=404)

    # 如果缓存里有 TMDB 的外部 URL，直接重定向过去
    cached_result = smart_image_cache.get(item_id)
    if cached_result and str(cached_result).startswith('http'):
        return requests.get(cached_result, stream=True).content

    target_id = cached_result if cached_result else item_id
    img_type = type
    params = "?maxWidth=1920&quality=80" if img_type.lower() == 'backdrop' else "?maxHeight=800&maxWidth=600&quality=90"
    
    # 🚨 第 1 级防御：强行转成剧集父级 ID，然后去请求
    if img_type.lower() == 'primary':
        target_id = get_real_image_id_robust(target_id)
        
    url = f"{host}/emby/Items/{target_id}/Images/{img_type}{params}&api_key={key}"
    try:
        resp = requests.get(url, timeout=5, stream=True)
        if resp.status_code == 200:
            return Response(content=resp.content, media_type=resp.headers.get("Content-Type", "image/jpeg"), headers={"Cache-Control": "public, max-age=86400"})
    except: pass

    clean_name = name.split(' - ')[0].strip() if name else ""

    # 🚨 第 2 级防御：名字搜 Emby 内部最新 ID
    if clean_name:
        try:
            search_url = f"{host}/emby/Items?SearchTerm={urllib.parse.quote(clean_name)}&IncludeItemTypes=Movie,Series,Episode&Recursive=true&api_key={key}"
            s_resp = requests.get(search_url, timeout=5)
            if s_resp.status_code == 200:
                items = s_resp.json().get("Items", [])
                if items:
                    new_id = items[0]["Id"]
                    if items[0]["Type"] in ["Episode", "Season", "Series"]:
                        new_id = get_real_image_id_robust(new_id)
                    smart_image_cache[item_id] = new_id 
                    
                    new_url = f"{host}/emby/Items/{new_id}/Images/{img_type}{params}&api_key={key}"
                    n_resp = requests.get(new_url, timeout=5, stream=True)
                    if n_resp.status_code == 200:
                        return Response(content=n_resp.content, media_type=n_resp.headers.get("Content-Type", "image/jpeg"), headers={"Cache-Control": "public, max-age=86400"})
        except: pass

    # 🚨 第 3 级防御：终极杀招！去 TMDB 拉取官方海报
    tmdb_key = cfg.get("tmdb_api_key")
    if clean_name and tmdb_key:
        try:
            proxy = cfg.get("proxy_url")
            proxies = {"https": proxy, "http": proxy} if proxy else None
            
            tmdb_url = f"https://api.themoviedb.org/3/search/multi?api_key={tmdb_key}&language=zh-CN&query={urllib.parse.quote(clean_name)}"
            t_resp = requests.get(tmdb_url, proxies=proxies, timeout=5)
            
            if t_resp.status_code == 200:
                results = t_resp.json().get("results", [])
                for res in results:
                    if res.get("media_type") in ["movie", "tv"]:
                        img_path = res.get("backdrop_path") if img_type.lower() == 'backdrop' else res.get("poster_path")
                        if img_path:
                            # 拿到 TMDB 真实图片链接
                            tmdb_img_url = f"https://image.tmdb.org/t/p/w500{img_path}"
                            smart_image_cache[item_id] = tmdb_img_url # 存入缓存
                            
                            # 代理返回这张图
                            final_resp = requests.get(tmdb_img_url, proxies=proxies, timeout=5, stream=True)
                            if final_resp.status_code == 200:
                                return Response(content=final_resp.content, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
                        break
        except Exception as e:
            logger.error(f"TMDB 终极兜底失败 [{clean_name}]: {e}")
            
    return Response(status_code=404)

@router.get("/api/proxy/user_image/{user_id}")
def proxy_user_image(user_id: str, tag: str = None):
    key = cfg.get("emby_api_key"); host = cfg.get("emby_host")
    if not key: return Response(status_code=404)
    try:
        url = f"{host}/emby/Users/{user_id}/Images/Primary?width=200&height=200&mode=Crop&quality=90&api_key={key}"
        if tag: url += f"&tag={tag}"
        resp = requests.get(url, timeout=3)
        if resp.status_code == 200:
            return Response(content=resp.content, media_type=resp.headers.get("Content-Type", "image/jpeg"))
    except: pass
    return Response(status_code=404)