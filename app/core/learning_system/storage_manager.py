# app/core/learning_system/storage_manager.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import json
import sqlite3
from datetime import datetime, timedelta


class StorageManager(ABC):
    """存储管理器抽象基类"""

    @abstractmethod
    async def store_metrics(self, metrics: Dict[str, Any]) -> bool:
        """存储指标数据"""
        pass

    @abstractmethod
    async def retrieve_metrics(self, content_id: str) -> Optional[Dict[str, Any]]:
        """检索指标数据"""
        pass

    @abstractmethod
    async def get_historical_data(self, days: int = 30) -> List[Dict[str, Any]]:
        """获取历史数据"""
        pass

    @abstractmethod
    async def store_learning_result(self, result: Dict[str, Any]) -> bool:
        """存储学习结果"""
        pass


class DatabaseStorageManager(StorageManager):
    """数据库存储管理器"""

    def __init__(self, db_path: str = "learning_data.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 创建指标表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS content_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_id TEXT UNIQUE,
                platform TEXT,
                collection_time TIMESTAMP,
                metrics_json TEXT,
                performance_score REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 创建学习结果表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS learning_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_type TEXT,
                result_json TEXT,
                timestamp TIMESTAMP,
                effectiveness_score REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    async def store_metrics(self, metrics: Dict[str, Any]) -> bool:
        """存储指标数据"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO content_metrics 
                (content_id, platform, collection_time, metrics_json, performance_score)
                VALUES (?, ?, ?, ?, ?)
            """, (
                metrics['content_id'],
                metrics['platform'],
                metrics['collection_time'],
                json.dumps(metrics),
                metrics.get('performance_score', 0)
            ))

            conn.commit()
            conn.close()

            return True
        except Exception as e:
            print(f"存储指标数据失败: {e}")
            return False

    async def retrieve_metrics(self, content_id: str) -> Optional[Dict[str, Any]]:
        """检索指标数据"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT metrics_json FROM content_metrics 
                WHERE content_id = ?
            """, (content_id,))

            row = cursor.fetchone()
            conn.close()

            if row:
                return json.loads(row[0])
            return None
        except Exception as e:
            print(f"检索指标数据失败: {e}")
            return None

    async def get_historical_data(self, days: int = 30) -> List[Dict[str, Any]]:
        """获取历史数据"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            since_date = datetime.now() - timedelta(days=days)

            cursor.execute("""
                SELECT metrics_json FROM content_metrics 
                WHERE collection_time >= ?
                ORDER BY collection_time DESC
            """, (since_date.isoformat(),))

            rows = cursor.fetchall()
            conn.close()

            return [json.loads(row[0]) for row in rows]
        except Exception as e:
            print(f"获取历史数据失败: {e}")
            return []


class CacheManager:
    """缓存管理器"""

    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self.local_cache = {}

    def get_from_cache(self, key: str) -> Optional[Any]:
        """从缓存获取数据"""
        # 先尝试Redis缓存
        if self.redis_client:
            try:
                cached_data = self.redis_client.get(key)
                if cached_data:
                    return json.loads(cached_data)
            except:
                pass

        # 再尝试本地缓存
        return self.local_cache.get(key)

    def set_cache(self, key: str, value: Any, expire_seconds: int = 3600):
        """设置缓存"""
        # 设置本地缓存
        self.local_cache[key] = value

        # 设置Redis缓存
        if self.redis_client:
            try:
                self.redis_client.setex(key, expire_seconds, json.dumps(value))
            except:
                pass