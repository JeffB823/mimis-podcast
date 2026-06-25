# Apple Podcastsへの公開手順

このプロジェクトはGitHub Pagesで音声とRSSフィードをセルフホストしています。Apple Podcasts Connectへ入力するURLは次のとおりです。

`https://jeffb823.github.io/mimis-podcast/feed.xml`

## 1. 配信サービスを用意する

Spotify for Creators、Buzzsprout、Transistor、Captivate、Libsynなど、Apple Podcasts対応のホスティングサービスを選びます。GitHubはソースコードの保管場所としては便利ですが、音声の配信、RSS生成、ダウンロード集計を担う通常のポッドキャストホストの代わりには向きません。

ホスト側で次を設定します。

- 番組名: `Mimi's Podcast`
- 日本語名: `ミミのポッドキャスト`
- 作者・ホスト名: Mimi、または公開したい正式名
- 言語: Japanese
- 番組形式: Episodic
- 更新頻度: Daily、または実際の配信頻度
- 主カテゴリー候補: News
- 副カテゴリー候補: Daily News、Health & Fitness、Education
- Explicit: No
- カバー画像: `artwork/mimis-podcast-cover-3000.jpg`
- 説明文:

> 海辺のバージニアビーチと古都・京都をつなぐ、日本語の朝のニュース番組。アメリカ国内、バージニアビーチ、京都、大相撲、ロサンゼルス・ドジャース、成熟女性の健康、日本語学習書の話題を、やわらかな京都のことばでコンパクトにお届けします。

## 2. 第1話をアップロードする

ホストに `output/2026-06-25/episode.mp3` をアップロードし、`output/2026-06-25/episode.json` のタイトルと説明を使います。公開前に、番組ページ、音量、冒頭と末尾、固有名詞の発音を確認してください。

## 3. RSSをテストする

ホストが発行したHTTPSのRSS URLをコピーします。Apple Podcastsアプリでは、ライブラリから「URLで番組を追加」を選び、登録前に表示と再生を確認できます。

RSSには最低でも、必要な番組タグ、カバー画像、公開済みのエピソード一件、直接取得できる音声ファイルが必要です。音声サーバーはHEADリクエストとbyte-rangeリクエストに対応している必要があります。

## 4. Apple Podcasts Connectへ提出する

1. https://podcastsconnect.apple.com/ に、二要素認証を有効にしたApple Accountでサインインします。
2. Add（＋）から New Show を選びます。
3. `Add a show with an RSS feed` を選びます。
4. ホストが発行したRSS URLを入力します。
5. Show Informationで、番組名、説明、作者、言語、カテゴリー、Explicit設定、画像を確認します。
6. Content Rightsで、音声、文章、画像、音楽などを配信する権利があることを確認します。
7. 連絡先を入力します。
8. Availabilityで配信する国・地域、公開日時、文字起こしの扱いを設定します。
9. Saveし、警告があればホスト側のRSSを修正します。
10. `Publish`を選び、Appleの審査へ送ります。

## 画像仕様

Appleが推奨する番組カバーは3000×3000ピクセルです。RSS経由では1400×1400から3000×3000まで受け付けられます。PNGまたはJPEG、正方形、透明部分なしが条件です。このプロジェクトの `artwork/mimis-podcast-cover-3000.jpg` は3000×3000のJPEGとして用意しています。

## 毎朝の公開

1. `python3 podcast.py run` で調査、台本、音声を生成します。
2. 台本の事実、健康表現、固有名詞、発音を人が確認します。
3. MP3、タイトル、説明をホストへアップロードします。
4. 公開時刻を設定します。
5. Apple Podcasts ConnectのAnalyticsで再生とフォローの動きを確認します。

## Apple公式資料

- 新しい番組を提出: https://podcasters.apple.com/support/897-submit-a-show
- RSS要件: https://podcasters.apple.com/support/823-podcast-requirements
- RSS検証: https://podcasters.apple.com/support/829-validate-your-podcast
- カバー画像: https://podcasters.apple.com/support/5514-show-cover-template
- RSSテスト: https://podcasters.apple.com/support/828-test-your-podcast
