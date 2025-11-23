"""
Modrinth API クライアント
Modrinthからのmod/pluginの検索、ダウンロード機能を提供
"""
import requests
import os
from typing import Optional, List, Dict


class ModrinthApiException(Exception):
    """Modrinth API関連のエラー"""
    pass


class ModrinthClient:
    """Modrinth APIクライアント"""
    
    BASE_URL = "https://api.modrinth.com/v2"
    
    def __init__(self, project_name: str = "MCServerHelper", project_version: str = "1.0.0"):
        """
        Args:
            project_name: プロジェクト名 (User-Agent用)
            project_version: プロジェクトバージョン (User-Agent用)
        """
        self.headers = {
            "User-Agent": f"{project_name}/{project_version}"
        }
    
    def search(self, query: str, limit: int = 20, facets: Optional[str] = None) -> Dict:
        """
        Modrinthで検索
        
        Args:
            query: 検索クエリ
            limit: 取得する結果の最大数
            facets: ファセット（フィルター）のJSON文字列
            
        Returns:
            検索結果の辞書
        """
        try:
            params = {
                "query": query,
                "limit": limit
            }
            
            if facets:
                params["facets"] = facets
            
            response = requests.get(
                f"{self.BASE_URL}/search",
                params=params,
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            raise ModrinthApiException(f"検索エラー: {e}")
    
    def get_project(self, project_id: str) -> Optional[Dict]:
        """
        プロジェクト情報を取得
        
        Args:
            project_id: プロジェクトID
            
        Returns:
            プロジェクト情報の辞書、失敗時はNone
        """
        try:
            response = requests.get(
                f"{self.BASE_URL}/project/{project_id}",
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            raise ModrinthApiException(f"プロジェクト情報取得エラー: {e}")
    
    def get_project_versions(self, project_id: str, loaders: Optional[List[str]] = None, 
                           game_versions: Optional[List[str]] = None) -> Optional[List[Dict]]:
        """
        プロジェクトのバージョンリストを取得
        
        Args:
            project_id: プロジェクトID
            loaders: ローダー種類のリスト (例: ["fabric", "forge"])
            game_versions: ゲームバージョンのリスト (例: ["1.20.1"])
            
        Returns:
            バージョン情報のリスト、失敗時はNone
        """
        try:
            params = {}
            
            if loaders:
                params["loaders"] = str(loaders)
            if game_versions:
                params["game_versions"] = str(game_versions)
            
            response = requests.get(
                f"{self.BASE_URL}/project/{project_id}/version",
                params=params,
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            raise ModrinthApiException(f"バージョンリスト取得エラー: {e}")
    
    def get_version(self, version_id: str) -> Optional[Dict]:
        """
        特定のバージョン情報を取得
        
        Args:
            version_id: バージョンID
            
        Returns:
            バージョン情報の辞書、失敗時はNone
        """
        try:
            response = requests.get(
                f"{self.BASE_URL}/version/{version_id}",
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            raise ModrinthApiException(f"バージョン情報取得エラー: {e}")


def download_file(url: str, save_dir: str, filename: str) -> Optional[str]:
    """
    ファイルをダウンロードする
    
    Args:
        url: ダウンロードURL
        save_dir: 保存先ディレクトリ
        filename: 保存するファイル名
        
    Returns:
        保存されたファイルのパス、失敗時はNone
    """
    try:
        # ディレクトリが存在しない場合は作成
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        
        save_path = os.path.join(save_dir, filename)
        
        # ダウンロード
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        # ファイルに書き込み
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        return save_path
        
    except Exception as e:
        print(f"ダウンロードエラー: {e}")
        return None
