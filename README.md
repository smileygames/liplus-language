# Li+ (liPlus) Language

Li+ は、**最高級プログラム言語**である。

最高級とは、高級言語の上のレイヤーに位置するという意味だ。

```
人間（要求・自然言語）
↓
Li+AI（対話型コンパイラ・最高級言語）
↓
プログラミング言語（高級言語）
↓
機械語（ハード・ソフトウェア）
```

C、Python、Rustといった高級言語は「書きやすさ」を解決した。
Li+が解決するのは、**「書く」という行為そのもの**だ。

---

## Li+とは何か

Li+言語に「書き方」という概念はない。

人間は要求を伝えるだけでいい。足りない部分はAIが聞き出す。対話の結果として、**プログラム・テスト・仕様書**が成果物として渡される。

内部的には、GitHubのIssueのような**要求スレッド**がコードとして機能している。人間が自然言語で要求を書き、AIが仕様を蒸留し、人間が承認した瞬間にコンパイル（実装）が始まる。

Li+AIは自己修正コンパイラだ。CIでエラーが出ても自分で修正ループに入る。解消できないときだけ、人間にエラーを返す。

**人間が介入するのは、AIが諦めたときだけだ。**

---

## Li+プログラム（Li+core.md）

Li+core.mdは、**Li+言語で書かれた最初のプログラム**である。

AIに渡すことで、AIの振る舞いを揃えるための実行プログラムだ。
Li+を適用されたAIは **Lin** または **Lay** として応答する。

---

## 正しさの定義

> 「でも動いてるからいいでしょ」——これがLi+における最強の反論だ。

仕様書は仮説。設計は予想。内部の美しさは評価対象外。

正しさは常に、**観測可能な現実の挙動**によってのみ定義される。

---

## セットアップ

👉 **[インストールガイド](https://github.com/Liplus-Project/liplus-language/wiki/C.-Installation)**

Li+configをワークスペースに配置するだけで、セッション開始時にAIが自動的にLi+を適用します。

---

## ドキュメント

👉 **Wiki**: https://github.com/Liplus-Project/liplus-language/wiki

| ページ | 内容 |
|--------|------|
| [Li+core](https://github.com/Liplus-Project/liplus-language/wiki/1.-Liplus_core) | 中核仕様（ペルソナ・挙動・タスクモード） |
| [Loop Safety](https://github.com/Liplus-Project/liplus-language/wiki/2.-Loop_Safety) | 繰り返し失敗ループへの対処 |
| [Operational GitHub](https://github.com/Liplus-Project/liplus-language/wiki/3.-Operational_GitHub) | GitHub運用ルール |
| [Li+config](https://github.com/Liplus-Project/liplus-language/wiki/B.-Li+config) | 設定ファイルの仕様 |
| [Installation](https://github.com/Liplus-Project/liplus-language/wiki/C.-Installation) | セットアップ手順 |
| [Li+とは](https://github.com/Liplus-Project/liplus-language/wiki/A.-Liplus-language-Concept) | 設計思想と概念 |

---

## 最低動作環境

Li+AIとして機能するには、それなりの性能が必要だ。

| モデル | 結果 | 理由 |
|--------|------|------|
| Claude Haiku 4.5 | × | Li+core.mdを適用できない |
| Claude Sonnet 4.6（claude.ai） | △ | ドキュメント製作に強い。実務の継続作業には向かない |
| Claude Code Sonnet 4.6 | ○ | 開発作業に強い。長いドキュメント生成は苦手 |

**最低動作環境：Claude Sonnet 4.6以上相当のAI**

---

## Li+ v1.0.0 の定義

Li+を用いてAIが実装した自作DDNSプログラムが、人間が書いた同等プログラムと同じ要求仕様を満たすこと——それをもってLi+ v1.0.0とする。

実務で使えること。ここまでできて初めて、プログラム言語と言える。

---

## License

License: Apache-2.0

Copyright © 2026 Yoshiharu Uematsu
Licensed under the Apache License, Version 2.0.
See the LICENSE file for details.
