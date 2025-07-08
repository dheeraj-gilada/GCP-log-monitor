"""
RuleParser: Loads and parses YARA-L rules for use in the rule engine.
"""
import os
import re
from typing import List, Dict

class RuleParser:
    def __init__(self, rules_dir: str):
        self.rules_dir = rules_dir

    def load_rules(self) -> List[str]:
        """Load all YARA-L rule files from the rules directory."""
        return [os.path.join(self.rules_dir, f) for f in os.listdir(self.rules_dir) if f.endswith('.yaral')]

    def parse_rule(self, rule_path: str) -> Dict:
        """Parse a YARA-L rule file and return a Python dict representing the rule meta-data and logic blocks."""
        rule = {}
        with open(rule_path, 'r') as f:
            content = f.read()
        # Extract meta section
        meta_match = re.search(r'meta:\s*([\s\S]*?)(?:events:|condition:|match:|$)', content)
        if meta_match:
            meta_block = meta_match.group(1)
            meta = {}
            for line in meta_block.splitlines():
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                m = re.match(r'(\w+)\s*=\s*"?([^"]*)"?', line)
                if m:
                    key, value = m.groups()
                    meta[key] = value
            rule['meta'] = meta
        else:
            rule['meta'] = {}
        # Extract events section
        events_match = re.search(r'events:\s*([\s\S]*?)(?:condition:|match:|$)', content)
        if events_match:
            events_block = events_match.group(1)
            rule['events'] = [line.strip() for line in events_block.splitlines() if line.strip() and not line.strip().startswith('#')]
        else:
            rule['events'] = []
        # Extract condition or match section
        cond_match = re.search(r'(condition|match):\s*([\s\S]*?)(?:$)', content)
        if cond_match:
            cond_block = cond_match.group(2)
            rule['condition'] = [line.strip() for line in cond_block.splitlines() if line.strip() and not line.strip().startswith('#')]
        else:
            rule['condition'] = []
        return rule 