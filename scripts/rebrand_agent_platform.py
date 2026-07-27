import os

target_dir = '/Users/abhisoni/Documents/Ad_Creator/forPublicgit'

def replace_in_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Replace occurrences of Gemini Enterprise Agent Platform with Gemini Enterprise Agent Platform
        c1 = content.replace('Gemini Enterprise Agent Platform', 'Gemini Enterprise Agent Platform')
        
        if c1 != content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(c1)
            print(f"Updated content in {filepath}")
    except Exception as e:
        pass

for root, _, files in os.walk(target_dir):
    for file in files:
        if file.endswith(('.md', '.yaml', '.html', '.py', '.txt', '.json', '.csv', '.js', '.ts', '.jsx', '.tsx')):
            replace_in_file(os.path.join(root, file))
