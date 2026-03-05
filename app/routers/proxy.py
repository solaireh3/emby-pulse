from fastapi import APIRouter, Response
from app.core.config import cfg
import requests
import urllib.parse
import logging

# 初始化日志
logger = logging.getLogger("uvicorn")
router = APIRouter()

# 🔥 新增：智能洗版图片兜底内存缓存 (Old_ID -> New_ID)
smart_image_cache = {}

def get_real_image_id_robust(item_id: str):
    """
    智能 ID 转换（暴力增强版）
    尝试多种姿势向 Emby 获取 SeriesId
    """
    key = cfg.get("emby_api_key")
    host = cfg.get("emby_host")
    if not key or not host: return item_id

    params_base = {"api_key": key}

    # 方案 A: 标准查询
    try:
        url_a = f"{host}/emby/Items/{item_id}"
        res_a = requests.get(url_a, params={**params_base, "Fields": "SeriesId,ParentId"}, timeout=3)
        if res_a.status_code == 200:
            data = res_a.json()
            if data.get("SeriesId"): return data['SeriesId']
            if data.get("Type") == "Episode" and data.get("ParentId"): return data['ParentId']
    except: pass

    # 方案 B: 祖先查询
    try:
        url_b = f"{host}/emby/Items/{item_id}/Ancestors"
        res_b = requests.get(url_b, params=params_base, timeout=3)
        if res_b.status_code == 200:
            for ancestor in res_b.json():
                if ancestor.get("Type") == "Series": return ancestor['Id']
                if ancestor.get("Type") == "Season" and not ancestor.get("SeriesId"): return ancestor['Id']
    except: pass

    # 方案 C: 列表查询
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

# ==========================================================
# 🔥 核心增强：彻底解决洗版裂图的“智能图片寻亲接口”
# ==========================================================
@router.get("/api/proxy/smart_image")
def proxy_smart_image(item_id: str, name: str = "", year: str = "", type: str = "Primary"):
    key = cfg.get("emby_api_key")
    host = cfg.get("emby_host")
    if not key or not host: return Response(status_code=404)

    # 1. 检查内存中是否有已经“认亲成功”的新 ID
    target_id = smart_image_cache.get(item_id, item_id)
    
    img_type = type
    params = "?maxWidth=1920&quality=80" if img_type.lower() == 'backdrop' else "?maxHeight=800&maxWidth=600&quality=90"
    
    # 2. 尝试直接获取 (或从缓存的新ID获取)
    url = f"{host}/emby/Items/{target_id}/Images/{img_type}{params}&api_key={key}"
    try:
        resp = requests.get(url, timeout=5, stream=True)
        if resp.status_code == 200:
            return Response(content=resp.content, media_type=resp.headers.get("Content-Type", "image/jpeg"), headers={"Cache-Control": "public, max-age=86400"})
    except: pass

    # 3. 🚨 触发洗版兜底机制：通过名字重新向 Emby 搜索最新的 ID
    if name:
        try:
            # 清洗名字 (去掉 ' - ' 后面的季集信息，只保留主标题)
            clean_name = name.split(' - ')[0].strip()
            search_url = f"{host}/emby/Items?SearchTerm={urllib.parse.quote(clean_name)}&IncludeItemTypes=Movie,Series,Episode&Recursive=true&api_key={key}"
            
            s_resp = requests.get(search_url, timeout=5)
            if s_resp.status_code == 200:
                items = s_resp.json().get("Items", [])
                if items:
                    # 抓取搜索到的第一个结果
                    new_id = items[0]["Id"]
                    
                    # 如果搜出来的是剧集/单集，进一步通过 robust 获取最准确的剧集封面 ID
                    if items[0]["Type"] in ["Episode", "Season", "Series"]:
                        new_id = get_real_image_id_robust(new_id)
                    
                    # 记录在缓存中，下次同一个历史记录直接用新ID秒出
                    smart_image_cache[item_id] = new_id 
                    
                    # 重新请求新ID的图片
                    new_url = f"{host}/emby/Items/{new_id}/Images/{img_type}{params}&api_key={key}"
                    n_resp = requests.get(new_url, timeout=5, stream=True)
                    if n_resp.status_code == 200:
                        return Response(content=n_resp.content, media_type=n_resp.headers.get("Content-Type", "image/jpeg"), headers={"Cache-Control": "public, max-age=86400"})
        except Exception as e:
            logger.error(f"图片寻亲兜底失败 [{name}]: {e}")
            
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