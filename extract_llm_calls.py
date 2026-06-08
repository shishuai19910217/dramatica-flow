
#!/usr/bin/env python3
"""Extract all LLM call locations and prompts from the project"""
import os
import re
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
LLM_CALL_PATTERNS = [
    r'llm\.complete\(\s*\[',
    r'LLMMessage\(',
]

def find_python_files():
    """Find all Python files in core and cli directories"""
    py_files = []
    for directory in ['core', 'cli']:
        dir_path = PROJECT_ROOT / directory
        if dir_path.exists():
            py_files.extend(dir_path.rglob('*.py'))
    return py_files

def extract_prompt_from_context(lines, start_idx):
    """Extract a prompt from the surrounding context"""
    # Look for prompt = f""" ... """ pattern
    prompt = []
    in_prompt = False
    quote_char = None
    
    # Search backwards to find prompt assignment
    search_back = min(start_idx, 100)
    for i in range(start_idx - search_back, start_idx + 1):
        if i &lt; 0 or i &gt;= len(lines):
            continue
            
        line = lines[i]
        
        # Look for prompt assignment
        if 'prompt = f"""' in line or 'prompt = """' in line:
            in_prompt = True
            quote_char = '"""'
            if 'f"""' in line:
                content = line.split('f"""', 1)[1]
            else:
                content = line.split('"""', 1)[1]
            prompt.append(content)
        elif in_prompt and '"""' in line:
            prompt.append(line.split('"""', 1)[0])
            break
        elif in_prompt:
            prompt.append(line)
    
    # If not found, look for system message in LLMMessage
    if not prompt:
        for i in range(start_idx, min(start_idx + 10, len(lines))):
            if 'LLMMessage("system"' in lines[i]:
                match = re.search(r'LLMMessage\("system",\s*"([^"]+)"\)', lines[i])
                if match:
                    return match.group(1)
    
    return '\n'.join(prompt).strip()

def analyze_file(file_path):
    """Analyze a single Python file for LLM calls"""
    try:
        content = file_path.read_text(encoding='utf-8')
        lines = content.split('\n')
    except Exception as e:
        return {
            'file': str(file_path.relative_to(PROJECT_ROOT)),
            'error': str(e),
            'calls': []
        }
    
    calls = []
    # Find all llm.complete calls
    for i, line in enumerate(lines):
        if 'llm.complete(' in line:
            # Look for LLMMessage calls in this context
            call_info = {
                'line': i + 1,
                'context': '',
                'prompt': '',
                'system_message': ''
            }
            
            # Extract context around the call
            context_start = max(0, i - 20)
            context_end = min(len(lines), i + 30)
            context_lines = lines[context_start:context_end]
            call_info['context'] = '\n'.join(context_lines)
            
            # Extract prompt
            call_info['prompt'] = extract_prompt_from_context(lines, i)
            
            # Look for system message
            for j in range(context_start, context_end):
                if 'LLMMessage("system"' in lines[j]:
                    match = re.search(r'LLMMessage\("system",\s*"([^"]+)"\)', lines[j])
                    if match:
                        call_info['system_message'] = match.group(1)
                    else:
                        # Multi-line system message
                        sys_msg = []
                        k = j
                        while k &lt; context_end and 'user' not in lines[k]:
                            sys_msg.append(lines[k])
                            k += 1
                        call_info['system_message'] = '\n'.join(sys_msg)
            
            calls.append(call_info)
    
    return {
        'file': str(file_path.relative_to(PROJECT_ROOT)),
        'calls': calls
    }

def main():
    print("=== LLM Call Analysis ===")
    print(f"Project root: {PROJECT_ROOT}")
    print()
    
    py_files = find_python_files()
    all_results = []
    
    print(f"Scanning {len(py_files)} Python files...")
    print()
    
    for file_path in py_files:
        result = analyze_file(file_path)
        all_results.append(result)
        
        if result.get('calls'):
            print(f"📄 {result['file']}")
            print(f"   Found {len(result['calls'])} LLM call(s)")
            print()
    
    # Generate comprehensive report
    report = {
        'summary': {
            'total_files_scanned': len(py_files),
            'total_llm_calls': sum(len(r.get('calls', [])) for r in all_results)
        },
        'results': all_results
    }
    
    report_file = PROJECT_ROOT / 'llm_calls_report.json'
    report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Full report saved to: {report_file}")
    print()
    
    # Also generate a readable markdown report
    md_report = "# LLM Call Analysis Report\n\n"
    md_report += f"Generated: {__import__('datetime').datetime.now()}\n\n"
    md_report += "## Summary\n\n"
    md_report += f"- Total files scanned: {report['summary']['total_files_scanned']}\n"
    md_report += f"- Total LLM calls: {report['summary']['total_llm_calls']}\n\n"
    
    md_report += "## Detailed Breakdown\n\n"
    
    for result in all_results:
        if result.get('error'):
            continue
            
        calls = result.get('calls', [])
        if not calls:
            continue
            
        md_report += f"### {result['file']}\n\n"
        
        for idx, call in enumerate(calls, 1):
            md_report += f"#### Call #{idx} (Line {call['line']})\n\n"
            
            if call.get('system_message'):
                md_report += "**System Message:**\n\n"
                md_report += "```\n" + call['system_message'] + "\n```\n\n"
            
            if call.get('prompt'):
                md_report += "**Prompt:**\n\n"
                md_report += "```\n" + call['prompt'][:2000]  # Truncate long prompts
                if len(call['prompt']) &gt; 2000:
                    md_report += "\n... (truncated)\n"
                md_report += "```\n\n"
            
            md_report += "---\n\n"
    
    md_report_file = PROJECT_ROOT / 'llm_calls_report.md'
    md_report_file.write_text(md_report, encoding='utf-8')
    print(f"Markdown report saved to: {md_report_file}")
    
    print()
    print("✅ Analysis complete!")

if __name__ == '__main__':
    main()

