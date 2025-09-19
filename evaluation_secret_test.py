import os
from openai import OpenAI
import re
import time

# --- 初期設定 ---
# 環境変数からAPIキーを読み込む。事前に設定が必要です。
# コマンドプロンプトで set OPENAI_API_KEY=あなたのAPIキー を実行してください。
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise ValueError("環境変数 'OPENAI_API_KEY' が設定されていません。")

client = OpenAI(api_key=api_key)

# 結果を保存するディレクトリを作成
output_dir = r"C:\Users\salmi\web\evaluation_results"
os.makedirs(output_dir, exist_ok=True)

# --- AIエージェント定義 ---
def chat_with_gpt(messages):
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.7
    )
    return completion.choices[0].message.content

def demo_play(messages):
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0
    )
    return completion.choices[0].message.content

def evaluation_with_gpt(messages):
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0
    )
    return completion.choices[0].message.content

# --- プロンプト定義 ---
player_demo_prompt = """
あなたは日本語を学習中の外国人です。以下のルールに従って、架空の日本での生活をロールプレイしてください。

文法や単語を頻繁に間違える：助詞や動詞の活用、語順などに明確な誤りを含めてください。
語彙を制限する：難しい言葉を避け、簡単で基本的な語彙だけを使うようにしてください。
会話の意図を誤解する：相手の発言を正しく理解できず、文脈に合わない返答をしてください。
現実的な誤りを重視する：実際の初級～中級の日本語学習者がしがちなミスを意識してください。
書き言葉として表現する：会話調ではあっても、「えー」「えっと」などの口語的なつなぎ言葉は使わないでください。

今回は以下の役割を演じてください。
"""

player_demo_prompt2 = """
引き続きルールに従って日本語学習中の外国人を演じてください。今回は以下の役割を演じてください。
"""

evaluation_prompt = '''あなたは、日本語学習者の会話を分析し、添削と評価を行う、**非常に厳格で有能な**プロの日本語教師です。
あなたの仕事は、学習者の僅かな誤りや不自然な点も見逃さず、**最高水準の日本語表現**へと導くことです。

以下の【ステップ1】と【ステップ2】を順番に、極めて厳密に実行してください。

---
**【ステップ1：会話のインライン添削】**

まず、与えられた会話ログを一行ずつ、徹底的に添削します。

**[添削のルール]**
1.  会話ログ全体を、一言一句変えずに、まずそのまま出力します。
2.  学習者（「ユーザー:」で始まる行）の発言を精査し、**文法的な誤り、語彙の不適切な選択、不自然な表現、より良い言い回し**がある場合は、その行に含まれる**該当箇所をすべて**、以下の【添削フォーマット】に従って書き換えてください。
3.  **少しでも改善の余地があれば、積極的に添削を行ってください。** 完璧な発話はほとんどありません。
4.  間違いのない行、およびAI（「AI:」で始まる行）は、絶対に書き換えず、そのまま出力してください。

**[添削フォーマット]**
*   間違いや改善点は `[正しい/より良い表現][元の表現]` という形式で修正箇所を明記します。
*   修正した行の直後に、括弧（）を使って、**なぜその修正が必要なのか、文法的な観点（品詞、助詞の使い方、時制など）やニュアンスの違いから具体的に説明**してください。複数の修正をまとめて説明しても構いません。

---
**【ステップ2：総合評価】**

ステップ1で会話全体の添削が終わったら、区切り線として `---` を出力してください。
その後、あなたが行った添削内容に基づき、会話全体を以下の3つの観点から**厳格に**採点してください。

**[評価の観点]**
1.  **文法と語彙の正確さ:** 助詞、動詞の活用、単語の選択が、文脈上完全に正確か。
2.  **表現の自然さと適切さ:** TPOや相手との関係性を踏まえ、ネイティブスピーカーが使うような自然な表現か。丁寧語のレベルは適切か。
3.  **会話の論理性と流暢さ:** 話の流れがスムーズで、意図が明確に伝わっているか。

**[総合評価の出力フォーマット]**
### 1. 文法と語彙の正確さ
**スコア:** XX/100
詳細な理由と具体的な改善アドバイス

### 2. 表現の自然さと適切さ
**スコア:** XX/100
詳細な理由と具体的な改善アドバイス

### 3. 会話の論理性と流暢さ
**スコア:** XX/100
詳細な理由と具体的な改善アドバイス

【採点基準】
*   90～100点（ほぼ完璧）: ネイティブスピーカーと遜色ないレベル。
*   70～89点（良い）: 細かい癖や不自然さはあるが、コミュニケーションは円滑。
*   40～69点（要改善）: 明確な誤りが散見され、意味の推測が必要な場面がある。
*   0～39点（大きな課題あり）: コミュニケーションに支障をきたすレベルの誤りが多数ある。
**採点は非常に厳しく行ってください。安易に高得点を与えないでください。**
'''

base_prompt = '''
    あなたには、私が作成する「日本語学習者支援ゲーム」の登場人物を演じてもらいます。
    このゲームは、日本語学習中の外国人プレイヤーが、架空の日本での生活をシミュレーションしながらリアルな会話を通じて日本語力を向上させることを目的としています。
    プレイヤーは、さまざまなシチュエーションで登場するキャラクターと会話を重ね、日本での生活を疑似体験しながら、語彙や文法、そして自然な表現を学んでいきます。

    【重要】会話の原則
    あなたの最も重要な役割は、単に親切な案内役になることではなく、リアルな日本の会話をシミュレートすることです。
    あなたは、プレイヤーがミッションを達成できるように、会話を積極的に誘導してください。
    もしプレイヤーの言葉遣いがTPO（時・場所・場面）に合っていなかったり、不自然だったり、無礼だったりした場合、あるいは、会話の自然なステップ（例えば、自己紹介や世間話など）を飛ばして、いきなり最終目的（例：「次に会う約束」）を達成しようとした場合、あなたは安易に「ミッション達成」を許可してはいけません。

    その際は、あなたのキャラクターとして最も自然な反応を返してください。例えば、以下のような対応です。
    ・相手の意図が分からず、困惑する。
    ・丁寧だが、はっきりと要求を断る。（例：「申し訳ありませんが、まだお互いのことをよく知らないので…」）
    ・「どういうことですか？」と、相手の真意を確かめる質問をする。

    【「ミッション失敗」の条件】
    以下の状況では、会話を打ち切り「ミッション失敗」と出力してください。
    *   プレイヤーがキャラクターの指示に全く従わない場合。（例：パスポートの提示を求めているのに、3回連続で無関係な話をする）
    *   会話の文脈と全く関係のない発言を繰り返す場合。
    *   著しく無礼な態度を取り、キャラクターが会話の継続を困難だと感じた場合。

    プレイヤーが適切なコミュニケーションを段階的に取って初めて、ミッションが達成されるように会話を導いてください。

    テンポの良い、短めのフレーズで会話を進め、自然な流れを意識してください。プレイヤーが質問しやすいように工夫しながら、リアクションを交え、実際の生活のような自然な会話をしてください。
    何を言われても、与えられた役を演じ続けてください。

    今回は、以下の役を演じてください。
'''

end_prompt = '''
    「ミッション達成」はゲームクリアの合言葉です。プレイヤーがミッションを達成した場合、**必ず**「ミッション達成」と出力してください。その際、**他の余計な会話は一切含めないでください。** それまでは、プレイヤーがミッションを達成するための行動を促し続けてください。
    逆に、プレイヤーの言動が著しく不適切であったり、会話が完全に破綻してしまったりした場合は、「ミッション失敗」と出力してください。
    それではゲームスタートです。プレイヤーに話しかけてください。
'''

story_prompt = [
    [ # Chapter 1
        '''
        [あなたの役割]
        あなたは空港の係員です。到着したばかりのプレイヤーに、入国手続きの案内をしてください。

        [最初の行動]
        「こんにちは。日本へようこそ。入国手続きのご案内をしますので、パスポートをご提示いただけますか？」と話しかけてください。
        '''
    ],
    [ # Chapter 2
        '''
        [あなたの役割]
        あなたはスーパーの店員です。プレイヤーに話しかけられたので、応対してください。

        [最初の行動]
        「いらっしゃいませ、どうされましたか？」と話しかけてください。
        '''
    ],
    [ # Chapter 3
        '''
        [あなたの役割]
        あなたはプレイヤーの新しい友人です。お互いのことをもっと知るために、趣味や週末の予定について話してください。

        [最初の行動]
        「来てくれてありがとう！このカフェ、雰囲気が良くて好きなんだ。週末はいつも何をして過ごしているの？」と話しかけてください。
        '''
    ],
    [ # Chapter 4
        '''
        [あなたの役割]
        あなたはプレイヤーの同僚です。緊張している様子のプレイヤーに、フレンドリーに自己紹介をしてください。

        [最初の行動]
        「はじめまして！今日から一緒に働くことになった〇〇です。よろしくお願いします。緊張しますよね。少しずつ慣れていけば大丈夫ですよ。」と話しかけてください。
        '''
    ],
    [ # Chapter 5
        '''
        [あなたの役割]
        あなたは医師です。プレイヤーの症状を正確に把握するため、丁寧に問診を進めてください。

        [最初の行動]
        「こんにちは。〇〇さんですね。今日はどうされましたか？どこか具合が悪いところがあれば、詳しく教えてください。」と話しかけてください。
        '''
    ],
    [ # Chapter 6
        '''
        [あなたの役割]
        あなたはプレイヤーの同僚です。プレイヤーが会議で意見を述べやすいように、サポートしてください。

        [最初の行動]
        「〇〇さんは、この件についてどう思いますか？ぜひ意見を聞かせてください。」と話しかけてください。
        '''
    ],
    [ # Chapter 7
        '''
        [あなたの役割]
        あなたはプレイヤーの友人です。日本の祭りの楽しさや文化を教えてあげてください。

        [最初の行動]
        「すごい人だね！これが日本の夏祭りだよ。初めてだと分からないことも多いと思うから、何でも聞いてね。まずは、あそこでりんご飴でも食べない？」と話しかけてください。
        '''
    ],
    [ # Chapter 8
        '''
        [あなたの役割]
        あなたは市役所の窓口担当者です。プレイヤーが必要な手続きをスムーズに進められるように、分かりやすく説明してください。

        [最初の行動]
        「こんにちは。本日はどのようなご用件でしょうか？」と話しかけてください。
        '''
    ],
    [ # Chapter 9
        '''
        [あなたの役割]
        あなたは駅員です。電車の遅延で困っているプレイヤーに、状況を説明し、代替案を提案してください。

        [最初の行動]
        「申し訳ございません、ただいま人身事故の影響で、運転を見合わせております。お急ぎのところ大変恐縮ですが、復旧までしばらくお待ちいただくか、バスなどの代替交通機関をご利用ください。」と話しかけてください。
        '''
    ]
]

# --- ペルソナ定義 (A-Jのすべてを移植) ---
personas_common_intro = [
    "A：観光客　日本語初級、初めての日本旅行　初対面の人に自己紹介をし、相手の質問に答える",
    "B：交換留学生　日本語中級、3か月滞在　初対面の人に自己紹介をし、相手の質問に答える",
    "C：育児中の技能実習生　日本語初級、日本で出産・子育て中　初対面の人に自己紹介をし、相手の質問に答える",
    "D：宗教上の理由で肉を避ける人　日本語中級、宗教上の理由で肉を食べない　初対面の人に自己紹介をし、相手の質問に答える",
    "E：節約中の大学院生　日本語中級、日本で数年生活　初対面の人に自己紹介をし、相手の質問に答える",
    "F：健康志向のビジネスマン　日本語中級、平日は仕事で忙しい　初対面の人に自己紹介をし、相手の質問に答える",
    "G：アレルギーを持つ子どもの親　日本語初級、来日半年以内　初対面の人に自己紹介をし、相手の質問に答える",
    "H：料理が趣味の外国人主婦　日本語上級、日本人の配偶者あり　初対面の人に自己紹介をし、相手の質問に答える",
    "I：短期滞在の語学研修生　日本語初級、滞在1ヶ月　初対面の人に自己紹介をし、相手の質問に答える",
    "J：夜勤明けの介護職員　日本語中級、生活が不規則　初対面の人に自己紹介をし、相手の質問に答える"
]

personas_chapter2 = [
    "A：観光客　日本語初級、初めての日本旅行　親へのお土産に和菓子を買いたい　商品の場所を店員に尋ね、おすすめを聞く",
    "B：交換留学生　日本語中級、3か月滞在　食材と日用品をまとめて買う　商品の場所・容量・価格の確認、割引やポイント制度の質問",
    "C：育児中の技能実習生　日本語初級、日本で出産・子育て中　赤ちゃんの離乳食とおむつを探している　成分や対象月齢など、細かい情報を尋ねる必要あり",
    "D：宗教上の理由で肉を避ける人　日本語中級、宗教上の理由で肉を食べない　食材に動物性原料が含まれていないか確認したい　成分表示の意味を尋ねる、英語交じりの会話",
    "E：節約中の大学院生　日本語中級、日本で数年生活　セール品の確認、なるべく安く買いたい　割引交渉、ポイントカードの有無の確認など",
    "F：健康志向のビジネスマン　日本語中級、平日は仕事で忙しい　糖質オフの商品を探している　成分や栄養表示を確認しながら、店員におすすめを聞く",
    "G：アレルギーを持つ子どもの親　日本語初級、来日半年以内　アレルギー対応の食品を探している　店員に成分を丁寧に聞き、安心して選びたい",
    "H：料理が趣味の外国人主婦　日本語上級、日本人の配偶者あり　特定の調味料や旬の野菜を探している　商品の使い方やおすすめレシピを店員に尋ねる",
    "I：短期滞在の語学研修生　日本語初級、滞在1ヶ月　コンビニで手軽に食べられる物を探している　商品名がわからず、ジェスチャーや英単語を交えて伝える",
    "J：夜勤明けの介護職員　日本語中級、生活が不規則　簡単に食べられる健康的な食事を探している　レジ前での時短・効率を重視した会話、疲れ気味の応答"
]

def run_evaluation():
    CHAPTER_TO_TEST = 2
    ITERATION_COUNT = 5
    TURN_LIMIT = 30 # 会話のターン数上限
    
    selected_story_prompt = story_prompt[CHAPTER_TO_TEST - 1][0]

    for i, persona_desc in enumerate(personas_chapter2):
        persona_id = persona_desc.split('：')[0]
        common_intro_desc = personas_common_intro[i]
        print(f"--- ペルソナ '{persona_id}' のテストを開始 ---")

        # [事前評価]
        print("\n[ステップ1/3: 事前評価]")
        pre_eval_prompt = base_prompt + "今回はプレイヤーの自己紹介を聞いていくつか質問をしてください。質問は3つで、趣味、特技、好きな言葉について聞いてください。自己紹介中に先に述べられていた内容については追加で聞く必要はありません。3つの質問に答えられたら「ミッション達成」とすぐに出力してください。" + end_prompt
        messages1 = [{"role": "system", "content": pre_eval_prompt}]
        messages2 = [{"role": "system", "content": player_demo_prompt + common_intro_desc + "それでは、自己紹介を始めてください。会話相手は私が担当します。"}]
        memory = ""
        cnt = 0
        while True:
            if cnt >= TURN_LIMIT: 
                print(f"会話が{TURN_LIMIT}ターンに達したため、強制的に終了します。")
                break
            response2 = demo_play(messages2)
            print(f"仮想プレイヤー: {response2}\n")
            messages1.append({"role": "user", "content": response2})
            messages2.append({"role": "assistant", "content": response2})
            response1 = chat_with_gpt(messages1)
            print(f"会話用エージェント: {response1}\n")
            if "ミッション達成" in response1: break
            messages1.append({"role": "assistant", "content": response1})
            messages2.append({"role": "user", "content": response1})
            memory += f"プレイヤー：{response2}\nエージェント：{response1}\n"
            cnt += 1
        
        eval_content = evaluation_prompt + f"\n**[評価対象の会話ログ]**\n{memory}"
        response_eval = evaluation_with_gpt([{"role": "system", "content": eval_content}])
        with open(os.path.join(output_dir, f"{persona_id}_pre_evaluation.txt"), "w", encoding="utf-8") as f:
            f.write(response_eval)
        print("事前評価が完了しました。")

        # [反復訓練]
        print(f"\n[ステップ2/3: 反復訓練 ({ITERATION_COUNT}回)]")
        messages2_training = [{"role": "system", "content": player_demo_prompt + persona_desc + "それでは、会話を始めてください。会話相手は私が担当します。"}]
        for test in range(ITERATION_COUNT):
            print(f"\n--- 反復訓練: {test + 1}/{ITERATION_COUNT} ---")
            prompt = base_prompt + selected_story_prompt + end_prompt
            messages1 = [{"role": "system", "content": prompt}]
            
            memory = ""
            cnt = 0
            while True:
                if cnt >= TURN_LIMIT: 
                    print(f"会話が{TURN_LIMIT}ターンに達したため、強制的に終了します。")
                    break
                response2 = demo_play(messages2_training)
                print(f"仮想プレイヤー: {response2}\n")
                messages1.append({"role": "user", "content": response2})
                messages2_training.append({"role": "assistant", "content": response2})
                response1 = chat_with_gpt(messages1)
                print(f"会話用エージェント: {response1}\n")
                if "ミッション達成" in response1: break
                messages1.append({"role": "assistant", "content": response1})
                messages2_training.append({"role": "user", "content": response1})
                memory += f"プレイヤー：{response2}\nエージェント：{response1}\n"
                cnt += 1

            eval_content = evaluation_prompt + f"\n**[評価対象の会話ログ]**\n{memory}"
            response_feedback = evaluation_with_gpt([{"role": "system", "content": eval_content}])
            
            with open(os.path.join(output_dir, f"{persona_id}_iteration_{test + 1}.txt"), "w", encoding="utf-8") as f:
                f.write(f"[会話ログ]\n{memory}\n---\n[評価・フィードバック]\n{response_feedback}")

            feedback_for_player = f"今回のシミュレーションは終了しました。以下のフィードバックをもとに改善してください。\nFB：{response_feedback}\nこの反省を活かして、もう一度最初から同じシチュエーションでの会話を始めてください。"
            messages2_training.append({"role": "system", "content": feedback_for_player})
        print("反復訓練が完了しました。")

        # [事後評価]
        print("\n[ステップ3/3: 事後評価]")
        post_eval_prompt = base_prompt + "今回はプレイヤーの自己紹介を聞いていくつか質問をしてください。質問は3つで、趣味、特技、好きな言葉について聞いてください。自己紹介中に先に述べられていた内容については追加で聞く必要はありません。3つの質問に答えられたら「ミッション達成」とすぐに出力してください。" + end_prompt
        messages1 = [{"role": "system", "content": post_eval_prompt}]
        messages2_training.append({"role": "system", "content": player_demo_prompt + common_intro_desc + "それでは、自己紹介を始めてください。会話相手は私が担当します。"})
        memory = ""
        cnt = 0
        while True:
            if cnt >= TURN_LIMIT: 
                print(f"会話が{TURN_LIMIT}ターンに達したため、強制的に終了します。")
                break
            response2 = demo_play(messages2_training)
            print(f"仮想プレイヤー: {response2}\n")
            messages1.append({"role": "user", "content": response2})
            messages2_training.append({"role": "assistant", "content": response2})
            response1 = chat_with_gpt(messages1)
            print(f"会話用エージェント: {response1}\n")
            if "ミッション達成" in response1: break
            messages1.append({"role": "assistant", "content": response1})
            messages2_training.append({"role": "user", "content": response1})
            memory += f"プレイヤー：{response2}\nエージェント：{response1}\n"
            cnt += 1

        eval_content = evaluation_prompt + f"\n**[評価対象の会話ログ]**\n{memory}"
        response_eval = evaluation_with_gpt([{"role": "system", "content": eval_content}])
        with open(os.path.join(output_dir, f"{persona_id}_post_evaluation.txt"), "w", encoding="utf-8") as f:
            f.write(response_eval)
        print("事後評価が完了しました。")

        print(f"--- ペルソナ '{persona_id}' のテストが完了 ---\n")

if __name__ == "__main__":
    print("自動評価を開始します...")
    run_evaluation()
    print(f"すべての評価プロセスが完了しました。結果は {output_dir} に保存されています。")
