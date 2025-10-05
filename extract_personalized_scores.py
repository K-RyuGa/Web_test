import os
import re
import csv

# --- 設定 ---
# ★パーソナライズ版の評価結果フォルダを指定
results_dir = r"C:\Users\salmi\web\evaluation_results_personalized"

# ★パーソナライズ版の出力CSVファイルを指定
output_csv_path = r"C:\Users\salmi\web\personalized_score_summary.csv"

def parse_score(text, category_name):
    """指定されたカテゴリのスコアを正規表現で抽出する"""
    pattern = re.compile(f"###\s*\d+\.?\s*{category_name}.*?^\*\*スコア:\*\*\s*(\d+)/100", re.MULTILINE | re.DOTALL)
    match = pattern.search(text)
    if match:
        return match.group(1)
    return "N/A"

def parse_filename_personalized(filename):
    """パーソナライズ版のファイル名からペルソナIDとフェーズを抽出する"""
    parts = filename.replace('.txt', '').split('_')
    # 例: ['A', 'personalized', 'iteration', '1']
    if len(parts) == 4 and parts[1] == 'personalized' and parts[2] == 'iteration':
        persona_id = parts[0]
        iteration_num = parts[3]
        phase = f"反復練習{iteration_num}回目"
        return persona_id, phase
    return None, None # マッチしないファイルは無視

def main():
    """メイン処理"""
    print(f"'{results_dir}' からパーソナライズ版の評価ファイルを読み込んでいます...")

    all_scores = []

    try:
        filenames = os.listdir(results_dir)
    except FileNotFoundError:
        print(f"エラー: ディレクトリが見つかりません: {results_dir}")
        print("先にパーソナライズ版の評価プログラムを実行して、結果ファイルを生成してください。")
        return

    for filename in filenames:
        if not filename.endswith(".txt"): 
            continue

        persona_id, phase = parse_filename_personalized(filename)
        if not persona_id:
            continue

        file_path = os.path.join(results_dir, filename)
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

            score_grammar = parse_score(content, "文法と語彙の正確さ")
            score_naturalness = parse_score(content, "表現の自然さと適切さ")
            score_fluency = parse_score(content, "会話の論理性と流暢さ")

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
        if '反復練習' in phase:
            match = re.search(r'(\d+)', phase)
            if match:
                order = int(match.group(1))
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
