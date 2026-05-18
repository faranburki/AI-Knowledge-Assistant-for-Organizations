import re

txt = open('pdf_content.txt', 'r', encoding='utf-8').read()

# Remove spaces between letters (PDF extraction artifact)
txt_cleaned = re.sub(r'(?<=[a-zA-Z])\s+(?=[a-zA-Z])', '', txt)

# Find the checklist section
checklist_start = txt_cleaned.find('MasterBuildChecklist')
if checklist_start == -1:
    print("Checklist not found!")
else:
    checklist_section = txt_cleaned[checklist_start:]
    
    # Extract all checklist items - match [ ], [x], [X], etc.
    items = re.findall(r'\[\s*([xX ]?)\s*\]\s+(.+?)(?=\n\[|\Z)', checklist_section, re.DOTALL)
    
    checked = 0
    unchecked = 0
    all_tasks = []
    
    for mark, task in items:
        # Clean up task text
        task_clean = ' '.join(task.split())
        if mark.lower().strip() == 'x':
            checked += 1
            all_tasks.append((True, task_clean))
        else:
            unchecked += 1
            all_tasks.append((False, task_clean))
    
    print("=" * 90)
    print("MASTER BUILD CHECKLIST ANALYSIS")
    print("=" * 90)
    print(f"\n✓ Completed Tasks: {checked}")
    print(f"  Remaining Tasks: {unchecked}")
    print(f"  Total Tasks: {checked + unchecked}")
    if checked + unchecked > 0:
        print(f"\nCompletion Rate: {100*checked/(checked+unchecked):.1f}%")
    print("\n" + "=" * 90)
    print("ALL TASKS BY PHASE:")
    print("=" * 90)
    
    # Group tasks by phase
    phases = {}
    for is_done, task in all_tasks:
        # Extract phase number from task (usually at the end)
        phase_match = re.search(r'(\d+)$', task)
        if phase_match:
            phase = phase_match.group(1)
            task_desc = task[:task.rfind(' ')].strip() if task.rfind(' ') > 0 else task
        else:
            phase = '?'
            task_desc = task
        
        if phase not in phases:
            phases[phase] = {'done': 0, 'total': 0, 'tasks': []}
        phases[phase]['total'] += 1
        if is_done:
            phases[phase]['done'] += 1
        phases[phase]['tasks'].append((is_done, task_desc))
    
    # Print by phase
    for phase in sorted(phases.keys(), key=lambda x: int(x) if x.isdigit() else 999):
        p = phases[phase]
        pct = 100 * p['done'] / p['total'] if p['total'] > 0 else 0
        print(f"\nPHASE {phase}: {p['done']}/{p['total']} ({pct:.0f}%)")
        for is_done, task in p['tasks'][:5]:
            status = "✓" if is_done else " "
            print(f"  [{status}] {task[:70]}")
        if len(p['tasks']) > 5:
            print(f"  ... and {len(p['tasks'])-5} more")

