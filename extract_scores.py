import os
import re
import csv

# --- 設定 ---
# 評価結果ファイルが保存されているディレクトリ
results_dir = r"C:\Users\salmi\web\evaluation_results"

# 出力するCSVファイル
output_csv_path = r"C:\Users\salmi\web\score_summary.csv"

def parse_score(text, category_name):
    """指定されたカテゴリのスコアを正規表現で抽出する"""
    # 正規表現パターン: 例) ### 1. 文法と語彙の正確さ
**スコア:** 85/100
    pattern = re.compile(f"###\s*\d+\.?\s*{category_name}.*?^\*\*スコア:\*\*\s*(\d+)/100", re.MULTILINE | re.DOTALL)
    match = pattern.search(text)
    if match:
        return match.group(1)
    return "N/A" # 見つからない場合は N/A を返す

def parse_filename(filename):
    """ファイル名からペルソナIDと評価フェーズを抽出する"""
    parts = filename.replace('.txt', '').split('_')
    persona_id = parts[0]
    phase = ''
    if len(parts) > 1:
        if parts[1] == 'iteration':
            phase = f"Iteration_{parts[2]}"
        elif parts[1] == 'pre':
            phase = "Pre-Evaluation"
        elif parts[1] == 'post':
            phase = "Post-Evaluation"
    return persona_id, phase

def main():
    """メイン処理"""
    print(f"'{results_dir}' から評価ファイルを読み込んでいます...")

    # 抽出したデータを格納するリスト
    all_scores = []

    # ディレクトリ内の全ファイルを確認
    try:
        filenames = os.listdir(results_dir)
    except FileNotFoundError:
        print(f"エラー: ディレクトリが見つかりません: {results_dir}")
        print("先に評価プログラムを実行して、結果ファイルを生成してください。")
        return

    for filename in filenames:
        if not filename.endswith(".txt"): 
            continue

        file_path = os.path.join(results_dir, filename)
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

            # ファイル名と内容から情報を抽出
            persona_id, phase = parse_filename(filename)
            score_grammar = parse_score(content, "文法と語彙の正確さ")
            score_naturalness = parse_score(content, "表現の自然さと適切さ")
            score_fluency = parse_score(content, "会話の論理性と流暢さ")

            # 抽出したデータを辞書としてリストに追加
            all_scores.append({
                'Persona': persona_id,
                'Phase': phase,
                'Score_Grammar': score_grammar,
                'Score_Naturalness': score_naturalness,
                'Score_Fluency': score_fluency,
                'Source_File': filename
            })
    
    if not all_scores:
        print("評価ファイルが見つかりませんでした。処理を終了します。")
        return

    # フェーズの順序に基づいてデータをソート
    def sort_key(d):
        persona = d['Persona']
        phase = d['Phase']
        order = 0
        if phase == 'Pre-Evaluation':
            order = 0
        elif 'Iteration' in phase:
            order = int(phase.split('_')[1])
        elif phase == 'Post-Evaluation':
            order = 99 # 最後にくるように大きな数字
        return (persona, order)

    all_scores.sort(key=sort_key)

    # CSVファイルに書き込み
    print(f"'{output_csv_path}' にスコアを書き込んでいます...")
    header = ['Persona', 'Phase', 'Score_Grammar', 'Score_Naturalness', 'Score_Fluency', 'Source_File']
    with open(output_csv_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=header)
        writer.writeheader()
        writer.writerows(all_scores)

    print("処理が完了しました。CSVファイルを確認してください。")

if __name__ == "__main__":
    main()
