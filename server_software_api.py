"""
MinecraftサーバーソフトウェアのダウンロードAPI統合クライアント
サポート: Vanilla, Paper, Purpur, Fabric, NeoForge, Forge
"""
import requests
import json
from typing import Optional, List, Dict, Tuple


class ServerSoftwareException(Exception):
    """サーバーソフトウェアAPI関連のエラー"""
    pass


class VanillaClient:
    """Minecraft Vanilla サーバー用APIクライアント"""
    
    MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
    
    def get_versions(self, version_type: str = "release") -> List[str]:
        """
        利用可能なバージョンのリストを取得
        
        Args:
            version_type: "release" または "snapshot"
            
        Returns:
            バージョンIDのリスト
        """
        try:
            response = requests.get(self.MANIFEST_URL, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if version_type == "release":
                return [v['id'] for v in data['versions'] if v['type'] == 'release']
            elif version_type == "snapshot":
                return [v['id'] for v in data['versions'] if v['type'] == 'snapshot']
            else:
                return [v['id'] for v in data['versions']]
                
        except requests.RequestException as e:
            raise ServerSoftwareException(f"Vanilla バージョン取得エラー: {e}")
    
    def get_download_url(self, version: str) -> Tuple[str, str]:
        """
        指定されたバージョンのダウンロードURLを取得
        
        Args:
            version: Minecraftバージョン (例: "1.21.1")
            
        Returns:
            (download_url, filename)のタプル
        """
        try:
            # マニフェストを取得
            response = requests.get(self.MANIFEST_URL, timeout=10)
            response.raise_for_status()
            manifest = response.json()
            
            # 指定されたバージョンを探す
            version_data = next(
                (v for v in manifest['versions'] if v['id'] == version),
                None
            )
            
            if not version_data:
                raise ServerSoftwareException(f"バージョン {version} が見つかりません")
            
            # バージョン詳細を取得
            version_url = version_data['url']
            response = requests.get(version_url, timeout=10)
            response.raise_for_status()
            version_info = response.json()
            
            # サーバーJARのダウンロードURL
            server_info = version_info.get('downloads', {}).get('server')
            if not server_info:
                raise ServerSoftwareException(f"バージョン {version} にはサーバーJARがありません")
            
            download_url = server_info['url']
            filename = f"server-vanilla-{version}.jar"
            
            return download_url, filename
            
        except requests.RequestException as e:
            raise ServerSoftwareException(f"Vanilla ダウンロードURL取得エラー: {e}")


class PaperClient:
    """PaperMC サーバー用APIクライアント"""
    
    BASE_URL = "https://api.papermc.io/v2"
    
    def get_versions(self) -> List[str]:
        """利用可能なバージョンのリストを取得"""
        try:
            response = requests.get(f"{self.BASE_URL}/projects/paper", timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get('versions', [])[::-1]  # 新しい順
            
        except requests.RequestException as e:
            raise ServerSoftwareException(f"Paper バージョン取得エラー: {e}")
    
    def get_builds(self, version: str) -> List[int]:
        """指定されたバージョンのビルドリストを取得"""
        try:
            response = requests.get(
                f"{self.BASE_URL}/projects/paper/versions/{version}",
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            return data.get('builds', [])[::-1]  # 新しい順
            
        except requests.RequestException as e:
            raise ServerSoftwareException(f"Paper ビルド取得エラー: {e}")
    
    def get_download_url(self, version: str, build: Optional[int] = None) -> Tuple[str, str]:
        """
        指定されたバージョンとビルドのダウンロードURLを取得
        
        Args:
            version: Minecraftバージョン
            build: ビルド番号 (Noneの場合は最新)
            
        Returns:
            (download_url, filename)のタプル
        """
        try:
            if build is None:
                # 最新ビルドを取得
                builds = self.get_builds(version)
                if not builds:
                    raise ServerSoftwareException(f"バージョン {version} のビルドがありません")
                build = builds[0]
            
            # ビルド情報を取得
            response = requests.get(
                f"{self.BASE_URL}/projects/paper/versions/{version}/builds/{build}",
                timeout=10
            )
            response.raise_for_status()
            build_data = response.json()
            
            # ダウンロード情報
            download_name = build_data['downloads']['application']['name']
            download_url = f"{self.BASE_URL}/projects/paper/versions/{version}/builds/{build}/downloads/{download_name}"
            
            return download_url, download_name
            
        except requests.RequestException as e:
            raise ServerSoftwareException(f"Paper ダウンロードURL取得エラー: {e}")


class PurpurClient:
    """Purpur サーバー用APIクライアント"""
    
    BASE_URL = "https://api.purpurmc.org/v2/purpur"
    
    def get_versions(self) -> List[str]:
        """利用可能なバージョンのリストを取得"""
        try:
            response = requests.get(self.BASE_URL, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get('versions', [])[::-1]  # 新しい順
            
        except requests.RequestException as e:
            raise ServerSoftwareException(f"Purpur バージョン取得エラー: {e}")
    
    def get_builds(self, version: str) -> List[str]:
        """指定されたバージョンのビルドリストを取得"""
        try:
            response = requests.get(f"{self.BASE_URL}/{version}", timeout=10)
            response.raise_for_status()
            data = response.json()
            builds = data.get('builds', {}).get('all', [])
            return [str(b) for b in builds[::-1]]  # 新しい順、文字列化
            
        except requests.RequestException as e:
            raise ServerSoftwareException(f"Purpur ビルド取得エラー: {e}")
    
    def get_download_url(self, version: str, build: Optional[str] = None) -> Tuple[str, str]:
        """
        指定されたバージョンとビルドのダウンロードURLを取得
        
        Args:
            version: Minecraftバージョン
            build: ビルド番号 (Noneの場合は最新)
            
        Returns:
            (download_url, filename)のタプル
        """
        try:
            if build is None or build == "latest":
                build = "latest"
            
            download_url = f"{self.BASE_URL}/{version}/{build}/download"
            filename = f"purpur-{version}-{build}.jar"
            
            return download_url, filename
            
        except Exception as e:
            raise ServerSoftwareException(f"Purpur ダウンロードURL取得エラー: {e}")


class FabricClient:
    """Fabric サーバー用APIクライアント"""
    
    META_URL = "https://meta.fabricmc.net/v2"
    LOADER_URL = "https://meta.fabricmc.net/v2/versions/loader"
    
    def get_game_versions(self) -> List[str]:
        """利用可能なMinecraftバージョンのリストを取得"""
        try:
            response = requests.get(f"{self.META_URL}/versions/game", timeout=10)
            response.raise_for_status()
            data = response.json()
            # stableバージョンのみを返す
            return [v['version'] for v in data if v.get('stable', False)]
            
        except requests.RequestException as e:
            raise ServerSoftwareException(f"Fabric ゲームバージョン取得エラー: {e}")
    
    def get_loader_versions(self) -> List[str]:
        """利用可能なFabric Loaderバージョンのリストを取得"""
        try:
            response = requests.get(f"{self.META_URL}/versions/loader", timeout=10)
            response.raise_for_status()
            data = response.json()
            return [v['version'] for v in data]
            
        except requests.RequestException as e:
            raise ServerSoftwareException(f"Fabric Loaderバージョン取得エラー: {e}")
    
    def get_download_url(self, game_version: str, loader_version: Optional[str] = None) -> Tuple[str, str]:
        """
        指定されたゲームバージョンとローダーバージョンのダウンロードURLを取得
        
        Args:
            game_version: Minecraftバージョン
            loader_version: Fabric Loaderバージョン (Noneの場合は最新)
            
        Returns:
            (download_url, filename)のタプル
        """
        try:
            if loader_version is None:
                # 最新のローダーバージョンを取得
                loader_versions = self.get_loader_versions()
                if not loader_versions:
                    raise ServerSoftwareException("Fabric Loaderバージョンが見つかりません")
                loader_version = loader_versions[0]
            
            # サーバーランチャーのダウンロードURL
            download_url = f"{self.LOADER_URL}/{game_version}/{loader_version}/1.0.1/server/jar"
            filename = f"fabric-server-{game_version}-{loader_version}.jar"
            
            return download_url, filename
            
        except Exception as e:
            raise ServerSoftwareException(f"Fabric ダウンロードURL取得エラー: {e}")


class NeoForgeClient:
    """NeoForge サーバー用APIクライアント"""
    
    MAVEN_METADATA_URL = "https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml"
    MAVEN_BASE_URL = "https://maven.neoforged.net/releases/net/neoforged/neoforge"
    
    def get_versions(self) -> List[str]:
        """利用可能なNeoForgeバージョンのリストを取得"""
        try:
            response = requests.get(self.MAVEN_METADATA_URL, timeout=10)
            response.raise_for_status()
            
            # XMLをパース
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.content)
            
            versions = []
            for version in root.findall('.//version'):
                versions.append(version.text)
            
            return versions[::-1]  # 新しい順
            
        except Exception as e:
            raise ServerSoftwareException(f"NeoForge バージョン取得エラー: {e}")
    
    def get_download_url(self, version: str) -> Tuple[str, str]:
        """
        指定されたバージョンのインストーラーダウンロードURLを取得
        
        Args:
            version: NeoForgeバージョン (例: "21.1.91")
            
        Returns:
            (download_url, filename)のタプル
        """
        try:
            # インストーラーのURLを構築
            filename = f"neoforge-{version}-installer.jar"
            download_url = f"{self.MAVEN_BASE_URL}/{version}/{filename}"
            
            return download_url, filename
            
        except Exception as e:
            raise ServerSoftwareException(f"NeoForge ダウンロードURL取得エラー: {e}")


class ForgeClient:
    """Minecraft Forge サーバー用APIクライアント"""
    
    MAVEN_METADATA_URL = "https://files.minecraftforge.net/net/minecraftforge/forge/maven-metadata.json"
    MAVEN_BASE_URL = "https://maven.minecraftforge.net/net/minecraftforge/forge"
    
    def get_versions_by_mc_version(self, mc_version: str) -> List[str]:
        """
        指定されたMinecraftバージョンに対応するForgeバージョンのリストを取得
        
        Args:
            mc_version: Minecraftバージョン (例: "1.20.1")
            
        Returns:
            Forgeバージョンのリスト
        """
        try:
            response = requests.get(self.MAVEN_METADATA_URL, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # 指定されたMinecraftバージョンに対応するForgeバージョンを抽出
            versions = []
            for mc_ver, forge_versions in data.items():
                if mc_ver == mc_version:
                    versions = forge_versions if isinstance(forge_versions, list) else [forge_versions]
                    break
            
            return versions
            
        except Exception as e:
            raise ServerSoftwareException(f"Forge バージョン取得エラー: {e}")
    
    def get_mc_versions(self) -> List[str]:
        """サポートされているMinecraftバージョンのリストを取得"""
        try:
            response = requests.get(self.MAVEN_METADATA_URL, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            return list(data.keys())
            
        except Exception as e:
            raise ServerSoftwareException(f"Forge Minecraftバージョン取得エラー: {e}")
    
    def get_download_url(self, mc_version: str, forge_version: Optional[str] = None) -> Tuple[str, str]:
        """
        指定されたMinecraftバージョンとForgeバージョンのインストーラーダウンロードURLを取得
        
        Args:
            mc_version: Minecraftバージョン
            forge_version: Forgeバージョン (Noneの場合は推奨バージョンまたは最新)
            
        Returns:
            (download_url, filename)のタプル
        """
        try:
            if forge_version is None:
                # 最新バージョンを取得
                versions = self.get_versions_by_mc_version(mc_version)
                if not versions:
                    raise ServerSoftwareException(f"Minecraftバージョン {mc_version} に対応するForgeが見つかりません")
                forge_version = versions[0]
            
            # フルバージョン文字列を構築 (例: 1.20.1-47.3.0)
            full_version = f"{mc_version}-{forge_version}"
            filename = f"forge-{full_version}-installer.jar"
            
            # 公式のダウンロードページURL (直接ダウンロードは広告ページを経由する必要がある)
            # 代わりにMavenリポジトリから直接取得
            download_url = f"{self.MAVEN_BASE_URL}/{full_version}/{filename}"
            
            return download_url, filename
            
        except Exception as e:
            raise ServerSoftwareException(f"Forge ダウンロードURL取得エラー: {e}")


# 統合クライアント
class ServerSoftwareClient:
    """全てのサーバーソフトウェアを統合したクライアント"""
    
    def __init__(self):
        self.vanilla = VanillaClient()
        self.paper = PaperClient()
        self.purpur = PurpurClient()
        self.fabric = FabricClient()
        self.neoforge = NeoForgeClient()
        self.forge = ForgeClient()
    
    def get_software_types(self) -> List[Dict[str, str]]:
        """利用可能なサーバーソフトウェアタイプのリストを取得"""
        return [
            {"id": "vanilla", "name": "Vanilla"},
            {"id": "paper", "name": "Paper"},
            {"id": "purpur", "name": "Purpur"},
            {"id": "fabric", "name": "Fabric"},
            {"id": "neoforge", "name": "NeoForge"},
            {"id": "forge", "name": "Forge"},
        ]
    
    def get_client(self, software_type: str):
        """指定されたソフトウェアタイプのクライアントを取得"""
        clients = {
            "vanilla": self.vanilla,
            "paper": self.paper,
            "purpur": self.purpur,
            "fabric": self.fabric,
            "neoforge": self.neoforge,
            "forge": self.forge,
        }
        
        client = clients.get(software_type)
        if not client:
            raise ServerSoftwareException(f"未対応のソフトウェアタイプ: {software_type}")
        
        return client
    
    def check_update_available(self, software_type: str, current_version: str, current_build: Optional[str] = None) -> Optional[Dict]:
        """
        指定されたサーバーソフトウェアの更新が利用可能かチェック
        
        Args:
            software_type: ソフトウェアタイプ
            current_version: 現在のバージョン
            current_build: 現在のビルド (オプション)
            
        Returns:
            更新が利用可能な場合は更新情報の辞書、なければNone
        """
        try:
            client = self.get_client(software_type)
            
            if software_type == "vanilla":
                # 最新のリリースバージョンを取得
                versions = client.get_versions("release")
                if versions and versions[0] != current_version:
                    return {
                        "software_type": software_type,
                        "current_version": current_version,
                        "latest_version": versions[0],
                        "update_available": True
                    }
                    
            elif software_type in ["paper", "purpur"]:
                # ビルドの更新をチェック
                if current_build:
                    builds = client.get_builds(current_version)
                    if builds and str(builds[0]) != str(current_build):
                        return {
                            "software_type": software_type,
                            "current_version": current_version,
                            "current_build": current_build,
                            "latest_build": builds[0],
                            "update_available": True
                        }
                        
            elif software_type == "fabric":
                # Loaderバージョンの更新をチェック
                if current_build:  # current_buildはloader_version
                    loader_versions = client.get_loader_versions()
                    if loader_versions and loader_versions[0] != current_build:
                        return {
                            "software_type": software_type,
                            "current_version": current_version,
                            "current_loader": current_build,
                            "latest_loader": loader_versions[0],
                            "update_available": True
                        }
                        
            elif software_type == "neoforge":
                # NeoForgeバージョンの更新をチェック
                versions = client.get_versions()
                if versions and versions[0] != current_version:
                    return {
                        "software_type": software_type,
                        "current_version": current_version,
                        "latest_version": versions[0],
                        "update_available": True
                    }
                    
            elif software_type == "forge":
                # Forgeバージョンの更新をチェック
                if current_build:  # current_buildはforge_version
                    forge_versions = client.get_versions_by_mc_version(current_version)
                    if forge_versions and forge_versions[0] != current_build:
                        return {
                            "software_type": software_type,
                            "current_mc_version": current_version,
                            "current_forge_version": current_build,
                            "latest_forge_version": forge_versions[0],
                            "update_available": True
                        }
            
            return None
            
        except Exception as e:
            raise ServerSoftwareException(f"更新チェックエラー: {e}")


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
    import os
    
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

