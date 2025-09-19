import os
import re

def parse_and_convert_to_html(text_content):
    html_body = ""
    lines = text_content.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith("---"):
            html_body += f"<h3>{line}</h3>\n"
            continue

        if line.startswith("ユーザー:"):
            msg_content = line.replace("ユーザー:", "").strip()
            
            reason_match = re.search(r"（(.+?)）$", msg_content)
            reason = ""
            if reason_match:
                reason = reason_match.group(1)
                msg_content = msg_content[:reason_match.start()].strip()

           # 正しい正規表現パターン
            pattern = r"\[(.*?)\]\[(.*?)\]"

            if re.search(pattern, msg_content):
                def create_diff_html(match):
                    correct = match.group(1)
                    wrong = match.group(2)
                    return f"<span style='text-decoration: line-through; color: gray;'>{wrong}</span> <span style='color: red; font-weight: bold;'>{correct}</span>"
                
                diff_line_html = re.sub(pattern, create_diff_html, msg_content)


                html_body += "<div style='margin-bottom: 1.5em; border: 1px solid #ddd; padding: 10px; border-radius: 5px;'>"
                html_body += "<b>ユーザー (添削結果):</b>"
                html_body += f"<div style='margin-bottom: 8px;'>{diff_line_html}</div>"
                if reason:
                    html_body += f"<div style='padding: 8px; background-color: #f0f0f0; border-radius: 4px; font-size: 0.9em; color: #555;'>💡 {reason}</div>"
                html_body += "</div>\n"
            else:
                html_body += f"<div><b>ユーザー:</b> {msg_content}</div>\n"
        
        elif line.startswith("AI:"):
            html_body += f"<div><b>AI:</b> {line.replace('AI:', '').strip()}</div>\n"
            
    return html_body

def main():
    target_dir = "C:\\Users\\salmi\\web\\eval_test"
    
    if not os.path.isdir(target_dir):
        print(f"Error: Directory not found at {target_dir}")
        return

    txt_files = [f for f in os.listdir(target_dir) if f.endswith('.txt')]
    
    if not txt_files:
        print(f"No .txt files found in {target_dir}")
        return

    print(f"Found {len(txt_files)} .txt files to convert.")

    for txt_file in txt_files:
        txt_path = os.path.join(target_dir, txt_file)
        html_path = os.path.splitext(txt_path)[0] + '.html'

        print(f"Converting {txt_file} to HTML...")

        try:
            with open(txt_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"  Error reading file: {e}")
            continue

        html_body_content = parse_and_convert_to_html(content)
        
        html_template = f"""
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{txt_file}</title>
    <style>
        body {{ font-family: sans-serif; line-height: 1.6; padding: 20px; }}
        h3 {{ border-bottom: 1px solid #ccc; padding-bottom: 5px; }}
    </style>
</head>
<body>
    <h1>{txt_file}</h1>
    {html_body_content}
</body>
</html>
"""

        try:
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_template)
            print(f"  Successfully created {html_path}")
        except Exception as e:
            print(f"  Error writing HTML file: {e}")

    print("\nConversion complete.")


if __name__ == '__main__':
    main()