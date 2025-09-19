import re
import os
from openai import OpenAI

def preprocess_line(line):
    """
    データセットの1行を評価エージェントが読める形式に前処理する関数。
    """
    # 時間情報、あいづち、非言語行動を除去
    line = re.sub(r'★.*?★', '', line)
    line = re.sub(r'〈.*?〉', '', line)
    line = re.sub(r'｛.*?｝', '', line)
    
    # 補足情報 ［...］ を除去
    line = re.sub(r'［.*?］', '', line)

    # 話者ラベルを変換
    if line.startswith('Ｔ：'):
        line = 'AI: ' + line[2:].strip()
    elif line.startswith('Ｉ：'):
        line = 'ユーザー: ' + line[2:].strip()
    else:
        return None # ラベルがない行は無視

    return line.strip()

def get_evaluation(client, conversation_log):
    """
    評価エージェントに会話ログを渡し、評価結果を取得する関数。
    """
    evaluation_prompt = '''あなたは、日本語学習者の会話を分析し、添削を行う、**非常に厳格で有能な**プロの日本語教師です。
あなたの仕事は、学習者の僅かな誤りや不自然な点も見逃さず、**最高水準の日本語表現**へと導くことです。

以下の【ステップ1】を極めて厳密に実行してください。
**出力は、【ステップ1】の添削結果のみとし、他の余計な文言は一切含めないでください。**

---
**【ステップ1：会話のインライン添削】**

与えられた会話ログを一行ずつ、徹底的に添削します。

**[添削のルール]**
1.  会話ログ全体を、一言一句変えずに、まずそのまま出力します。
2.  学習者（「ユーザー:」で始まる行）の発言を精査し、誤り、より良い表現がある場合は、その行に含まれる**該当箇所をすべて**、以下の【添削フォーマット】に従って書き換えてください。
3.  **少しでも改善の余地があれば、積極的に添削を行ってください。** 完璧な発話はほとんどありません。
4.  間違いのない行、およびAI（「AI:」で始まる行）は、絶対に書き換えず、そのまま出力してください。   

**[添削フォーマット]**
*   間違いや改善点は `[正しい/より良い表現][元の表現]` という形式で修正箇所を明記します。
*   修正した行の直後に、括弧（）を使って、**なぜその修正が必要なのか、文法的な観点（品詞、助詞の使い方、時制など）やニュアンスの違いから具体的に説明**してください。複数の修正をまとめて説明しても構いません。
*   意味が分からない支離滅裂な文章についても必ず推測で補ってください。
'''


    scenario_title = "インタビュー"
    scenario_description = "ユーザーは、日本語学習に関するインタビューを受けています。インタビュアーからの質問に、あなたの考えや経験を日本語で答えてください。"
    
    eval_user_content = f"""

**[評価対象の状況]**
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
            temperature=0,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"--- ERROR ---\nAn error occurred: {e}\n--- END ERROR ---"

def main():
    # --- List of input files ---
    input_files = [
        #"C:\\Users\\salmi\\Game\\test-data\\43\\43＿韓国＿女性＿滞在期間2か月＿学習期間5か月＿初級ー上.txt",
        "C:\\Users\\salmi\\Game\\test-data\\96\\96＿韓国＿男性＿滞在期間1か月＿学習期間1か月＿初級ー上.txt",
        "C:\\Users\\salmi\\Game\\test-data\\97\\97＿韓国＿男性＿滞在期間1か月＿学習期間1か月＿初級ー上.txt",
        "C:\\Users\\salmi\\Game\\test-data\\103\\103＿台湾＿男性＿滞在期間1か月＿学習期間3か月＿初級ー中.txt",
        "C:\\Users\\salmi\\Game\\test-data\\118\\118＿韓国＿男性＿滞在期間1か月＿学習期間3か月＿初級ー中.txt"
    ]
    output_dir = "C:\\Users\\salmi\\web\\eval_test"
    chunk_size = 6
    # --------------------------

    os.makedirs(output_dir, exist_ok=True)

    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set.")
        return
        
    client = OpenAI()

    for input_file in input_files:
        print(f"\n--- Processing file: {os.path.basename(input_file)} ---")
        
        dataset_name = os.path.basename(input_file)
        output_file = os.path.join(output_dir, f"GPT訂正_{dataset_name}")

        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except FileNotFoundError:
            print(f"Error: Input file not found at {input_file}")
            continue

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"--- Evaluation Start ---\nInput File: {input_file}\nChunk Size: {chunk_size}\n\n")

        chunk_count = 0
        for i in range(0, len(lines), chunk_size):
            chunk_count += 1
            chunk = lines[i:i + chunk_size]
            
            processed_lines = [preprocess_line(line) for line in chunk]
            processed_lines = [line for line in processed_lines if line]

            if not processed_lines:
                continue

            conversation_log = "\n".join(processed_lines)
            
            print(f"Evaluating chunk {chunk_count} for {dataset_name}...")

            evaluation_result = get_evaluation(client, conversation_log)

            with open(output_file, 'a', encoding='utf-8') as f:
                last_line_of_chunk = ""
                if chunk:
                    last_line_of_chunk = chunk[-1].strip()

                f.write(f"--- Chunk {chunk_count} (Last line: {last_line_of_chunk}) ---\n")
                f.write(evaluation_result + "\n\n")
        
        print(f"Evaluation complete for {dataset_name}. Results saved to {output_file}")

    print("\nAll files processed.")


if __name__ == '__main__':
    main()