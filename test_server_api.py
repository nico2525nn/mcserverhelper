"""
server_software_api.pyの簡単なテストスクリプト
"""
from server_software_api import ServerSoftwareClient, ServerSoftwareException

def test_api():
    print("=== サーバーソフトウェアAPI テスト ===\n")
    
    client = ServerSoftwareClient()
    
    # 1. ソフトウェアタイプ一覧
    print("1. サポートされているソフトウェアタイプ:")
    types = client.get_software_types()
    for t in types:
        print(f"   - {t['name']} ({t['id']})")
    print()
    
    # 2. Vanilla のバージョン取得テスト
    print("2. Vanilla の最新5バージョン:")
    try:
        vanilla_versions = client.vanilla.get_versions("release")
        for ver in vanilla_versions[:5]:
            print(f"   - {ver}")
    except ServerSoftwareException as e:
        print(f"   エラー: {e}")
    print()
    
    # 3. Paper のバージョン取得テスト
    print("3. Paper の最新5バージョン:")
    try:
        paper_versions = client.paper.get_versions()
        for ver in paper_versions[:5]:
            print(f"   - {ver}")
    except ServerSoftwareException as e:
        print(f"   エラー: {e}")
    print()
    
    # 4. Purpur のバージョン取得テスト
    print("4. Purpur の最新5バージョン:")
    try:
        purpur_versions = client.purpur.get_versions()
        for ver in purpur_versions[:5]:
            print(f"   - {ver}")
    except ServerSoftwareException as e:
        print(f"   エラー: {e}")
    print()
    
    # 5. Fabric の��ームバージョン取得テスト
    print("5. Fabric の最新5ゲームバージョン:")
    try:
        fabric_versions = client.fabric.get_game_versions()
        for ver in fabric_versions[:5]:
            print(f"   - {ver}")
    except ServerSoftwareException as e:
        print(f"   エラー: {e}")
    print()
    
    # 6. NeoForge のバージョン取得テスト
    print("6. NeoForge の最新5バージョン:")
    try:
        neoforge_versions = client.neoforge.get_versions()
        for ver in neoforge_versions[:5]:
            print(f"   - {ver}")
    except ServerSoftwareException as e:
        print(f"   エラー: {e}")
    print()
    
    # 7. ダウンロードURL取得テスト (Vanilla)
    print("7. Vanilla 最新バージョンのダウンロードURL取得テスト:")
    try:
        vanilla_versions = client.vanilla.get_versions("release")
        if vanilla_versions:
            url, filename = client.vanilla.get_download_url(vanilla_versions[0])
            print(f"   バージョン: {vanilla_versions[0]}")
            print(f"   ファイル名: {filename}")
            print(f"   URL: {url[:50]}..." if len(url) > 50 else f"   URL: {url}")
    except ServerSoftwareException as e:
        print(f"   エラー: {e}")
    print()
    
    # 8. Paper のビルド取得テスト
    print("8. Paper の最新バージョンのビルド取得テスト:")
    try:
        paper_versions = client.paper.get_versions()
        if paper_versions:
            builds = client.paper.get_builds(paper_versions[0])
            print(f"   バージョン: {paper_versions[0]}")
            print(f"   最新5ビルド: {builds[:5]}")
    except ServerSoftwareException as e:
        print(f"   エラー: {e}")
    print()
    
    print("=== テスト完了 ===")

if __name__ == "__main__":
    test_api()
