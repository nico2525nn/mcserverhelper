Modrinth の **`GET /version/{id}`** では、各ファイルについて少なくとも `hashes`、`url`、`filename`、`primary`、`size`、`file_type` が取れますが、`file_type` は `sources-jar` / `dev-jar` / `javadoc-jar` / `required-resource-pack` などに限られており、**mod / plugin を直接表すフィールドではありません**。なので、**Modrinth API だけで「この JAR は mod か plugin か」をファイル単位で確定するのは難しく、実際には推論か JAR 内部のメタデータ確認が必要**です。([Modrinth Documentation][1])

Modrinth 側でまず使うべき情報は、`/project/{id}` の `project_type`（`mod` / `modpack` / `resourcepack` / `shader`）と `loaders`、それから `/version/{id}` の `loaders` と `files[].filename` です。さらに Modrinth には loader 一覧のエンドポイントがあり、loader ごとに対応する project type も返します。つまり、**一覧・検索段階では project_type と loaders でかなり絞れる**一方、**最終確定は別手段が必要**という構造です。([Modrinth Documentation][2])

実装の境界としては、次の考え方が現実的です。
**一次判定**: Modrinth の project/version メタデータだけで絞る。
**二次判定**: JAR の中身を見て、実際の loader メタを確認する。
この二段構えにしているランチャー実装・議論は実際にあります。PrismLauncher の issue では、`mods.toml` と `fabric.mod.json` の両方が入った JAR で、現状は `mods.toml` 側が使われる挙動が報告されています。別の issue では、`fabric.mod.json` / `mods.toml` / `neoforge.mods.toml` を読んで依存関係や非互換を先にチェックしたい、という要望も出ています。つまり、**「検索時点で完全に判別」は狙わず、曖昧なものだけ内部メタを読む**のが実装上の共通解に近いです。([GitHub][3])

JAR 内で見るべき代表的な識別子は、少なくとも次です。
Fabric は `fabric.mod.json` が JAR ルートにあることを前提にしています。Forge は `META-INF/mods.toml` を使います。NeoForge は `META-INF/neoforge.mods.toml` を使います。Paper の plugin は `plugin.yml` を使い、`plugin-yml` 系の Gradle プラグインでは `paper-plugin.yml` や `bungee.yml` も生成対象です。したがって、**「mod 系」か「plugin 系」かの識別は、実務上はこれらのメタファイルの有無を見るのが基本**です。([Fabric Wiki][4])

既存コードや参考実装を探すなら、まず見るべき場所は以下です。
PrismLauncher の issue / code 周辺は、**どの順番でメタを読んでいるか**や、**複数メタが同居したときの扱い**を見るのに有用です。MultiMC 系・PrismLauncher 系はこの手の判定で実例として参考になります。加えて、`@xmcl/mod-parser` は Forge / Liteloader / Fabric / Quilt のメタを解析するライブラリとして公開されているので、**「既存のパーサを流用する」方向で見る価値があります**。([GitHub][3])

コーディングAIに渡す用の要点だけ抜くと、こんな方針になります。
「Modrinth API の `project_type` / `loaders` / `version.loaders` / `files[].filename` / `files[].hashes` / `files[].url` / `files[].size` でまず候補を絞る。`GET /version/{id}` の `file_type` は mod/plugin 判定には使えない。曖昧な JAR だけをダウンロードして、ZIP 内の `fabric.mod.json`、`META-INF/mods.toml`、`META-INF/neoforge.mods.toml`、`plugin.yml`、`paper-plugin.yml`、`velocity-plugin.json` 等を確認する。複数メタがある場合は ambiguous 扱いにする。実装前に PrismLauncher の issue 2364 と 450、そして `@xmcl/mod-parser` を確認する。」([Modrinth Documentation][2])

追加で調べるなら、まず見る順番はこの3つが効率的です。

1. Modrinth の `projects` / `versions` / `tags loader` の公式ドキュメント。
2. PrismLauncher の該当 issue と、その周辺の parser 実装。
3. `@xmcl/mod-parser` の実装と README。
   これで、**API でどこまでやるか**と**JAR 内部解析をどこに入れるか**の線引きがかなり固まります。([Modrinth Documentation][2])

必要なら次に、これをそのまま AI に投げられるように「仕様メモ形式」に整形します。

[1]: https://docs.modrinth.com/api/operations/getversion/ "Get a version | Modrinth Documentation"
[2]: https://docs.modrinth.com/api/operations/getproject/ "Get a project | Modrinth Documentation"
[3]: https://github.com/PrismLauncher/PrismLauncher/issues/2364 "Mod metadata parser does not respect installed loader for instance · Issue #2364 · PrismLauncher/PrismLauncher · GitHub"
[4]: https://wiki.fabricmc.net/documentation%3Afabric_mod_json?utm_source=chatgpt.com "fabric.mod.json"
