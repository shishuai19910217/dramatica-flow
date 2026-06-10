with open(r'd:\owned\ai\xiaoshuo\dramatica-flow\core\narrative\__init__.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = '- 第 8 章 - 真相大白\r\n\r\n## 番茄爆款硬性规则'
new = '''- 第 8 章 - 真相大白

**禁止事项**（违反将导致审计不通过）：
- 禁止重复使用相同的动词/形容词/名词组合（如连续出现"无意""按时""无视"）
- 禁止模式化句式（如"XX 无意/XX 按时/XX 无视"这种循环重复）
- 禁止同一序列内出现重复或高度相似的标题
- 每章标题必须反映该章独有的核心冲突或关键转折
- 如果序列围绕同一事件，请从不同角度命名（如：图书馆冲突->"禁书争夺"->"规则破解"->"管理员现身"->"真相一角"）

## 番茄爆款硬性规则'''

if old in content:
    content = content.replace(old, new)
    with open(r'd:\owned\ai\xiaoshuo\dramatica-flow\core\narrative\__init__.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Success!')
else:
    print('Pattern not found!')
    # Show what we have
    import re
    match = re.search(r'- 第 8 章.{0,50}', content)
    if match:
        print('Found pattern:', repr(match.group(0)))
