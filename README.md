# ミミのポッドキャスト — Mimi's Podcast

![Mimi's Podcast cover](artwork/mimis-podcast-cover.png)

平日の朝に届ける、約12〜15分の日本語ニュース・ポッドキャストです。短いオープニング、主要トピック、各分野の要点、「今日覚えておきたいこと」、穏やかな締めくくり、というモーニングブリーフ形式で構成します。

話し方は、全国の日本語話者が無理なく理解できる標準語を土台に、やわらかな京都の言い回しと間合いを少しだけ添えます。誇張した方言や、芸者・舞妓を連想させる演技にはしません。

## 毎日の構成

1. オープニングと日付
2. 30秒のトップニュース
3. アメリカ国内ニュース
4. バージニアビーチのニュース
5. 京都のニュース
6. 大相撲
7. ロサンゼルス・ドジャース
8. 成熟女性の健康
9. 日本語学習書の新刊・書評
10. 今日のまとめと締めくくり

健康コーナーは教育目的です。診断や個別の治療指示はせず、デトックス・クレンズの宣伝文句を事実として扱いません。緊急性のある症状や治療判断については医療専門家への相談を促します。

## セットアップ

Python 3.10以上と `ffmpeg` が必要です。このMacには `ffmpeg` が見つかっています。

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
export OPENAI_API_KEY="your-key"
```

APIキーはチャットやファイルに貼り付けず、環境変数として設定してください。

## 使い方

その日の調査、台本、音声をまとめて生成します。

```bash
python3 podcast.py run
```

日付を指定する場合:

```bash
python3 podcast.py run --date 2026-06-25
```

調査と台本だけ:

```bash
python3 podcast.py script
```

既存の台本から音声だけ:

```bash
python3 podcast.py audio --script output/2026-06-25/script.txt
```

成果物は `output/YYYY-MM-DD/` に保存されます。

- `research.md`: 引用付きの調査メモ
- `sources.json`: 参照URL
- `script.txt`: 読み上げ用の日本語台本
- `episode.mp3`: 完成音声
- `audio-parts/`: 分割された音声

## 第1話

2026年6月25日版は `output/2026-06-25/` にあります。台本、出典付き調査メモ、エピソード情報、約13分26秒のMP3を収録しています。この初回MP3は、APIキーが未設定のため、macOSの日本語音声 Kyoko を使って作成しました。

Apple Podcastsへの公開方法は [APPLE_PODCASTS.md](APPLE_PODCASTS.md) を参照してください。

## 公開RSSフィード

GitHub Pagesで番組ページとRSSを公開しています。

- 番組ページ: `https://jeffb823.github.io/mimis-podcast/`
- Apple Podcastsへ登録するRSS: `https://jeffb823.github.io/mimis-podcast/feed.xml`

## 編集方針

- 「最新」は生成日の絶対日付とタイムゾーンを基準に確認します。
- 速報は、確認済みの事実と未確認情報を明確に分けます。
- 試合がない日は、無理に結果を作らず、次戦・順位・負傷者情報などを扱います。
- 大相撲の本場所がない期間は、番付、巡業、けが、部屋・協会の公式発表を優先します。
- 医療情報は公的機関、医学会、査読研究、大学病院などを優先します。
- 書評は広告文の言い換えにせず、対象レベル、長所、弱点、向いている学習者を伝えます。

## カスタマイズ

番組名、長さ、モデル、声、各コーナーの扱いは [config.json](./config.json) で変更できます。番組の編集・話し方の詳細は [prompts/editorial.md](./prompts/editorial.md) にあります。
