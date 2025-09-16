import argparse
import re
import os
from openai import OpenAI

def preprocess_line(line):
    """
    データセットの1行を評価エージェントが読める形式に前処理する関数。
    """
    # 音声記号や相槌などを除去
    line = re.sub(r'〈.*?〉', '', line)
    line = re.sub(r'｛.*?｝', '', line)
    
    # 読み方が併記されている部分を整形 (例: かんこくー［韓国］ -> 韓国)
    line = re.sub(r'[^［］]*?［(.*?)］', r'\1', line)

    # 話者ラベルを変換
    if line.startswith('Ｔ：'):
        # インタビュアー (Tester) を AI 役とする
        line = 'AI: ' + line[2:].strip()
    elif line.startswith('Ｉ：'):
        # 学習者 (Interviewee) を ユーザー 役とする
        line = 'ユーザー: ' + line[2:].strip()
    else:
        # 話者ラベルがない行は無視
        return None

    return line.strip()

def get_evaluation(client, conversation_log):
    """
    評価エージェントに会話ログを渡し、評価結果を取得する関数。
    """
    evaluation_prompt = '''
        あなたは、日本語学習者の会話を評価する、非常に厳格で専門的な日本語教師です。
        あなたの唯一のタスクは、提供された会話ログを、後述するルールに極めて厳密に従って評価し、指定された【出力フォーマット】で結果を返すことです。

        これから与えられる会話ログは、実際の音声会話を文字に起こしたものです。そのため、話し言葉特有の表現やノイズが含まれることを前提として評価してください。

        **【最重要ルール：評価対象外の項目】**
        以下の項目は、会話評価において完全に無視し、フィードバックで絶対に言及してはいけません。これらについて言及した場合、あなたの評価は失敗とみなされます。
        1.  **フィラーや言い淀み:** 「あー」「えー」「あのー」といった単語。これらは自然な発話の一部であり、評価対象ではありません。
        2.  **個人情報等の代替記号:** `【姓名Ｂ】`のような記号。これらは文脈に応じて意味を補完し、記号の存在自体には触れないでください。

        （悪いフィードバックの例：「えー、というフィラーが多いのが気になりました。」）
        （良いフィードバックの例：フィラーには一切触れず、文法や語彙の間違いのみを指摘する。）

        **【重要】評価の手順**
        1.  まず、与えられた「評価対象の状況」をよく読み、会話の背景（誰と、どこで、何をしているか）を完全に理解します。
        2.  次に、その状況を踏まえた上で会話全体を「1. 文法と語彙」「2. TPOと丁寧さ」「3. 会話の自然な流れ」の3つの観点から詳細に分析します。
        3.  採点基準に基づいて各観点を100点満点で採点します。
        4.  最後に、下記の【出力フォーマット】に従って、プレイヤーへのフィードバックを生成します。

        **【観点別の採点基準】**

        **1. 文法と語彙**
        *   90-100点：文法や語彙の誤りがほとんどなく、非常に自然で適切。
        *   70-89点：助詞などの細かい誤りは見られるが、意図は明確に伝わる。
        *   40-69点：誤りが多く、相手が意味を推測する必要がある場面がある。
        *   0-39点：誤りが多すぎて、コミュニケーションが困難。

        **2. TPOと丁寧さ**
        *   90-100点：TPO（時・場所・場面）や相手との関係性に応じた言葉遣いが完璧。
        *   70-89点：丁寧さの選択にやや不自然な点があるが、大きな問題はない。
        *   40-69点：TPOにそぐわない言葉遣いや、不適切な丁寧さが目立つ。
        *   0-39点：TPOを著しく無視した、または無礼な言葉遣い。

        **3. 会話の自然な流れ**
        *   90-100点：会話の流れがスムーズで、目的達成までのやり取りに無駄がない。
        *   70-89点：目的は達成できているが、返答に時折詰まったり、不自然な間があったりする。
        *   40-69点：会話がぎこちなく、対話が噛み合わないことがある。
        *   0-39点：会話が全く成立していない、または目的から大きく逸脱している。
        *   **※注意：この評価には、フィラー（あー、えー等）の有無は含めないでください。あくまで会話の論理的な流れや、やり取りのテンポを評価してください。**

        **【出力フォーマット】**
        以下のMarkdownフォーマットを厳守し、各観点のスコアとフィードバックを出力してください。

        ### 1. 文法と語彙
        **スコア:** XX/100
        **フィードバック:**
        *   **気になった点・改善点:** （もし改善すべき点や、より自然な表現にするための提案があれば、具体的な部分を引用し、どのように改善できるかを複数、具体的に説明。なければ「特になし」と記述してください。）

        ---

        ### 2. TPOと丁寧さ
        **スコア:** XX/100
        **フィードバック:**
        *   **気になった点・改善点:** （もし改善すべき点や、より自然な表現にするための提案があれば、具体的な部分を引用し、どのように改善できるかを複数、具体的に説明。なければ「特になし」と記述してください。）

        ---

        ### 3. 会話の自然な流れ
        **スコア:** XX/100
        **フィードバック:**
        *   **気になった点・改善点:** （もし改善すべき点や、より自然な表現にするための提案があれば、具体的な部分を引用し、どのように改善できるかを複数、具体的に説明。なければ「特になし」と記述してください。）
    '''
    
    scenario_title = "インタビュー"
    scenario_description = "あなたは、日本語学習に関するインタビューを受けています。インタビュアーからの質問に、あなたの考えや経験を日本語で答えてください。"
    
    eval_user_content = f"""**[評価対象の状況]**
シナリオ: {scenario_title}
状況設定: {scenario_description}

**[会話ログ]**
{conversation_log}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": evaluation_prompt},
                {"role": "user", "content": eval_user_content}
            ],
            temperature=0.25,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"--- ERROR ---\nAn error occurred: {e}\n--- END ERROR ---"


def main():
    # --- Hardcoded values ---
    input_file = "C:\\Users\\salmi\\Game\\test-data\\43\\43＿韓国＿女性＿滞在期間2か月＿学習期間5か月＿初級ー上.txt"
    output_file = "C:\\Users\\salmi\\Game\\test-data\\43\\test_e.txt"
    chunk_size = 12
    # --------------------------

    # APIキーが環境変数に設定されているか確認
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set.")
        return
        
    # clientを初期化。APIキーは自動で環境変数から読み込まれる
    client = OpenAI()

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Error: Input file not found at {input_file}")
        return

    # 出力ファイルを空の状態で準備
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"--- Evaluation Start ---\nInput File: {input_file}\nChunk Size: {chunk_size}\n\n")

    chunk_count = 0
    for i in range(0, len(lines), chunk_size):
        chunk_count += 1
        chunk = lines[i:i + chunk_size]
        
        processed_lines = [preprocess_line(line) for line in chunk]
        # Noneを除外
        processed_lines = [line for line in processed_lines if line]

        if not processed_lines:
            continue

        conversation_log = "\n".join(processed_lines)
        
        print(f"Evaluating chunk {chunk_count}...")

        evaluation_result = get_evaluation(client, conversation_log)

        with open(output_file, 'a', encoding='utf-8') as f:
            last_line_of_chunk = ""
            if chunk:
                last_line_of_chunk = chunk[-1].strip()

            f.write(f"--- Chunk {chunk_count} (Last line: {last_line_of_chunk}) ---\n")
            f.write(evaluation_result + "\n\n")
    
    print(f"Evaluation complete. Results saved to {output_file}")


if __name__ == '__main__':
    main()
