# asset-publisher

Blender で作った3Dアセットを、複数の販売先へまとめて出品するツールです。
販売先は `publish.yaml` の `enabled` でオン・オフを切り替えられます。

## 対応している販売先

| 販売先 | 方式 | やってくれること | 人がやること |
|---|---|---|---|
| Sketchfab | API | 下書きでモデルをアップロード | 3D表示を調整して公開 |
| CGTrader | API | 下書き作成、画像・ファイル添付 | 内容確認、AI使用の申告、公開 |
| Etsy | API | ダウンロード商品の下書き作成、画像・ファイル添付 | 内容確認して公開 |
| itch.io | butler | ファイルのアップロード・更新 | ページは最初に手で作る |
| Fab | キット | zip・画像・入力文面・チェックリストを作成 | 画面で入力して審査に出す |
| BOOTH | キット | 同上（日本語・円建て） | 画面で入力して公開 |
| Cults3D | キット | 同上 | 画面で入力して公開 |

API がある販売先も**下書きまで**しか作りません。公開ボタンは必ず人が押す前提です。

## 使い方

```bash
pip install -e .

asset-publisher targets                                   # オン・オフ一覧
asset-publisher publish assets/*/listing.yaml             # リハーサル（送信しない。送る予定の内容を表示）
asset-publisher publish assets/*/listing.yaml --live      # 実際に送る
```

### オン・オフの切り替え

| やりたいこと | 方法 |
|---|---|
| 普段使う販売先を決める | `publish.yaml` の `enabled: true / false` |
| 今回だけこの販売先に絞る | `--only sketchfab,fab`（`enabled` は無視） |
| 今回だけ追加する | `--enable etsy` |
| 今回だけ外す | `--disable booth` |
| CI から指定する | 環境変数 `PUBLISH_ONLY=sketchfab,fab` |

適用順は「設定ファイル → `--only`（または `PUBLISH_ONLY`）→ `--enable` → `--disable`」です。

### 2回目以降

`.publish-state.json` に、どの販売先に何のバージョンを何のIDで出したかが記録されます（コミットしてください）。

- 同じバージョンでもう一度実行 → スキップ
- `listing.yaml` の `version` を上げて実行 → 既存の出品を更新
- `--force` → 出品済みでも新規作成し直す

キット型の販売先で出品が終わったら、URLを記録しておくと次回から更新扱いになります。

```bash
asset-publisher record assets/danchi_5f/listing.yaml fab --url https://www.fab.com/listings/xxxx
```

## ファイル

- `publish.yaml`：販売先ごとのオン・オフと設定
- `assets/<名前>/listing.yaml`：1アセット分の出品情報（タイトル・説明は日英、価格はドルと円）。サンプルは `examples/danchi_5f/`
- 認証情報は環境変数で渡します（`SKETCHFAB_API_TOKEN`、`CGTRADER_ACCESS_TOKEN`、`ETSY_API_KEY`、`ETSY_ACCESS_TOKEN`、`BUTLER_API_KEY`）。`--live` のときだけ必要です。

## 販売先を足すとき

`asset_publisher/adapters/` に `Adapter`（API型）か `KitAdapter`（キット型）を継承したクラスを作り、
`adapters/__init__.py` の `ADAPTERS` に足すだけです。`check`（事前チェック）、`create`（新規）、`update`（更新）の3つを書きます。

## claude-starter テンプレートとつなぐ

`project.mk` の deploy をこれにすると、main にマージして承認ボタンを押した時点で各販売先に下書きが揃います。

```make
project-deploy:
	@test "$$CI" = "true" || (echo "make deploy は CI からのみ実行できます" && exit 1)
	asset-publisher publish assets/*/listing.yaml --live
```

`deploy.yml` の Deploy ステップには、`production` Environment の Secrets から認証情報を渡します。

```yaml
        env:
          SKETCHFAB_API_TOKEN: ${{ secrets.SKETCHFAB_API_TOKEN }}
          CGTRADER_ACCESS_TOKEN: ${{ secrets.CGTRADER_ACCESS_TOKEN }}
          PUBLISH_ONLY: ${{ vars.PUBLISH_ONLY }}   # リポジトリ変数で販売先を切り替えたい場合
```

`.publish-state.json` を CI で更新した場合は、コミットして push し直す処理を追加してください。
キット（`dist/publish/`）は Artifacts として保存しておくと、CI 実行後にダウンロードして手作業に使えます。

## 注意・未確認の点

- **CGTrader**：下書き作成時のフィールド名（`title`・`description`・`tags`・`prices`・`category_id`）は、公開されている更新APIの例から推測しています。最初の `--live` の前に API ドキュメントと照らし合わせてください。AI 使用の申告を API で行う方法は確認できなかったので、画面での申告をメモに出しています。
- **Etsy**：`when_made` の値やタグの渡し方は、実際の API の応答を見て調整が必要な場合があります。
- **Sketchfab**：既存モデルの更新はタイトルや説明などの情報だけで、モデルファイルは差し替えられません。ファイルを変えたときは `--force` で新規作成してください。
- テストはすべて通信をモックしたものです。実際の販売先にはまだ接続していません。最初は各販売先を1つずつ `--only` で試してください。
