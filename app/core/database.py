import sqlite3
import os
import requests
import json
from app.core.config import cfg, DB_PATH

def init_db():
    db_dir = os.path.dirname(DB_PATH)
    if not os.path.exists(db_dir):
        try: os.makedirs(db_dir, exist_ok=True)
        except: pass

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 0. 播放记录表
        c.execute('''CREATE TABLE IF NOT EXISTS PlaybackActivity (Id INTEGER PRIMARY KEY AUTOINCREMENT, UserId TEXT, UserName TEXT, ItemId TEXT, ItemName TEXT, PlayDuration INTEGER, DateCreated DATETIME DEFAULT CURRENT_TIMESTAMP, Client TEXT, DeviceName TEXT)''')
        # 1. 机器人配置表
        c.execute('''CREATE TABLE IF NOT EXISTS users_meta (user_id TEXT PRIMARY KEY, expire_date TEXT, note TEXT, created_at TEXT)''')
        # 2. 邀请码表
        c.execute('''CREATE TABLE IF NOT EXISTS invitations (code TEXT PRIMARY KEY, days INTEGER, used_count INTEGER DEFAULT 0, max_uses INTEGER DEFAULT 1, created_at TEXT, used_at DATETIME, used_by TEXT, status INTEGER DEFAULT 0, template_user_id TEXT)''')
        try: c.execute("ALTER TABLE invitations ADD COLUMN template_user_id TEXT")
        except: pass
        # 3. 日历表
        c.execute('''CREATE TABLE IF NOT EXISTS tv_calendar_cache (id TEXT PRIMARY KEY, series_id TEXT, season INTEGER, episode INTEGER, air_date TEXT, status TEXT, data_json TEXT)''')
        # 4. 求片主表
        c.execute('''CREATE TABLE IF NOT EXISTS media_requests (tmdb_id INTEGER, media_type TEXT, title TEXT, year TEXT, poster_path TEXT, status INTEGER DEFAULT 0, season INTEGER DEFAULT 0, reject_reason TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (tmdb_id, season))''')
        # 5. 求片用户表
        c.execute('''CREATE TABLE IF NOT EXISTS request_users (id INTEGER PRIMARY KEY AUTOINCREMENT, tmdb_id INTEGER, user_id TEXT, username TEXT, season INTEGER DEFAULT 0, requested_at DATETIME DEFAULT CURRENT_TIMESTAMP, UNIQUE(tmdb_id, user_id, season))''')
        # 6. 盘点忽略表
        c.execute('''CREATE TABLE IF NOT EXISTS insight_ignores (item_id TEXT PRIMARY KEY, item_name TEXT, ignored_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        # 7. 缺集记录表
        c.execute('''CREATE TABLE IF NOT EXISTS gap_records (id INTEGER PRIMARY KEY AUTOINCREMENT, series_id TEXT, series_name TEXT, season_number INTEGER, episode_number INTEGER, status INTEGER DEFAULT 0, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, UNIQUE(series_id, season_number, episode_number))''')

        conn.commit()
        conn.close()
        print("✅ 数据库结构初始化完成.")
    except Exception as e: 
        print(f"❌ DB Init Error: {e}")

# ==========================================
# 🔥 核心防御武器：伪装 SQLite Row 类
# 解决 API 返回的 Dict 不支持 row[0] 或大小写问题导致的静默崩溃！
# ==========================================
class APIRow:
    def __init__(self, d):
        self._d = d
        self._keys = list(d.keys())
        self._vals = list(d.values())
        
    def keys(self):
        return self._keys
        
    def __getitem__(self, key):
        # 1. 支持原生索引访问，如 row[0]
        if isinstance(key, int):
            try: return self._vals[key]
            except IndexError: return None
            
        # 2. 支持不区分大小写的键名访问，如 row['userid'] 和 row['UserId']
        key_lower = str(key).lower()
        for k, v in self._d.items():
            if str(k).lower() == key_lower:
                return v
        return None

def _interpolate_sql(query: str, args) -> str:
    """将带有 ? 的 SQL 模板和元组参数转换为完整的 SQL 字符串，供 API 穿透使用"""
    if not args: return query
    parts = query.split('?')
    if len(parts) - 1 != len(args): return query
    res = parts[0]
    for i, arg in enumerate(args):
        if isinstance(arg, bool): val = "1" if arg else "0"
        elif isinstance(arg, (int, float)): val = str(arg)
        elif arg is None: val = "NULL"
        else: val = f"'{str(arg).replace(chr(39), chr(39)+chr(39))}'"
        res += val + parts[i+1]
    return res

def query_db(query, args=(), one=False):
    # ==========================================
    # 🔥 双擎路由拦截器 (API 穿透模式)
    # ==========================================
    mode = cfg.get("playback_data_mode", "sqlite")
    is_playback_query = "PlaybackActivity" in query or "PlaybackReporting" in query
    
    if mode == "api" and is_playback_query:
        host = cfg.get("emby_host")
        token = cfg.get("emby_api_key")
        if host and token:
            full_sql = _interpolate_sql(query, args)
            
            print(f"\n[API 引擎] 🚀 拦截到播放库查询，发起穿透...")
            print(f"[API 引擎] 📜 执行 SQL: {full_sql}")
            
            url = f"{host.rstrip('/')}/emby/user_usage_stats/submit_custom_query"
            headers = {"X-Emby-Token": token, "Content-Type": "application/json"}
            payload = {"CustomQueryString": full_sql}
            
            try:
                res = requests.post(url, headers=headers, json=payload, timeout=20)
                print(f"[API 引擎] 📡 收到响应状态码: {res.status_code}")
                
                if res.status_code == 200:
                    raw_data = None
                    try:
                        res_json = res.json()
                        # 应对 Emby 插件的二次套娃字符串
                        if isinstance(res_json, str):
                            try: raw_data = json.loads(res_json)
                            except: raw_data = res_json
                        else:
                            raw_data = res_json
                    except Exception as parse_e:
                        print(f"[API 引擎] ⚠️ JSON 第一次解析失败: {parse_e}")
                        try: raw_data = json.loads(res.text)
                        except: raw_data = []
                    
                    if isinstance(raw_data, dict):
                        raw_data = raw_data.get("results", raw_data.get("Items", [raw_data]))
                        
                    if raw_data is None:
                        raw_data = []
                    
                    if not isinstance(raw_data, list):
                        raw_data = [raw_data]
                        
                    print(f"[API 引擎] ✅ 成功解析数据条数: {len(raw_data)}")
                    
                    # 🔥 致命修复：将普通 dict 包装为 APIRow，完美欺骗业务层
                    data = [APIRow(item) if isinstance(item, dict) else item for item in raw_data]

                    if query.strip().upper().startswith("SELECT"):
                        return (data[0] if data else None) if one else data
                    return True
                else:
                    print(f"[API 引擎] ❌ 接口拒绝请求! 响应: {res.text[:200]}")
            except Exception as e:
                print(f"[API 引擎] ❌ 网络崩溃异常: {e}")
        else:
            print("[API 引擎] ⚠️ 未配置 Emby Host 或 Token，自动降级为 SQLite 直读")
            
    # ==========================================
    # 🚂 原版 SQLite 执行器 (处理非播放表及降级情况)
    # ==========================================
    if not os.path.exists(DB_PATH): 
        print(f"[SQLite 引擎] ⚠️ 数据库文件不存在: {DB_PATH}")
        return None
        
    try:
        conn = sqlite3.connect(DB_PATH, timeout=20.0)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(query, args)
        if query.strip().upper().startswith("SELECT"):
            rv = cur.fetchall()
            conn.close()
            return (rv[0] if rv else None) if one else rv
        else:
            conn.commit()
            conn.close()
            return True
    except Exception as e: 
        print(f"[SQLite 引擎] ❌ 查询崩溃: {e} | Query: {query}")
        return None

def get_base_filter(user_id_filter):
    where = "WHERE 1=1"
    params = []
    
    if user_id_filter and user_id_filter != 'all':
        where += " AND UserId = ?"
        params.append(user_id_filter)
    
    hidden = cfg.get("hidden_users")
    if (not user_id_filter or user_id_filter == 'all') and hidden and len(hidden) > 0:
        placeholders = ','.join(['?'] * len(hidden))
        where += f" AND UserId NOT IN ({placeholders})"
        params.extend(hidden)
        
    return where, params