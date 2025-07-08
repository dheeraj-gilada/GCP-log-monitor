"""
RuleEngine: Loads, manages, and applies rules to normalized logs.
"""
from typing import List, Dict
from .rule_parser import RuleParser
import re

class RuleEngine:
    def __init__(self, rules_dir: str):
        self.parser = RuleParser(rules_dir)
        self.rules = self._load_rules()

    def _load_rules(self) -> List[Dict]:
        """Load and parse all rules from the rules directory."""
        rule_paths = self.parser.load_rules()
        return [self.parser.parse_rule(path) for path in rule_paths]

    def match(self, log: Dict) -> List[Dict]:
        """Apply all loaded rules to a normalized log. Return list of matched rule meta dicts."""
        matches = []
        for rule in self.rules:
            if self._rule_matches_log(rule, log):
                matches.append(rule['meta'])
        return matches

    def _rule_matches_log(self, rule: Dict, log: Dict) -> bool:
        # Enhanced matcher: supports =, contains, matches (regex), case-insensitive
        for event_line in rule.get('events', []):
            event_line = event_line.strip()
            print(f"[DEBUG] Evaluating event line: {event_line}")
            # OR logic: split on ' or ' and match if any sub-condition is true
            if ' or ' in event_line:
                sub_conditions = [s.strip('() ') for s in event_line.split(' or ')]
                or_match = False
                for sub in sub_conditions:
                    # Try equality
                    m_eq = re.match(r'\$(\w+(?:\.\w+)*)\s*=\s*"([^"]+)"', sub)
                    if m_eq:
                        key_path, expected_value = m_eq.groups()
                        keys = key_path.split('.')
                        value = log
                        for k in keys:
                            if isinstance(value, dict) and k in value:
                                value = value[k]
                            else:
                                print(f"[DEBUG] Key '{k}' not found in log for equality check.")
                                break
                        else:
                            result = str(value).lower() == expected_value.lower()
                            print(f"[DEBUG] [OR] Equality check: log[{key_path}]='{value}' == '{expected_value}'? {result}")
                            if result:
                                or_match = True
                                break
                    # Try contains
                    m_contains = re.match(r'\$(\w+(?:\.\w+)*)\s*contains\s*"([^"]+)"', sub)
                    if m_contains:
                        key_path, expected_value = m_contains.groups()
                        keys = key_path.split('.')
                        value = log
                        for k in keys:
                            if isinstance(value, dict) and k in value:
                                value = value[k]
                            else:
                                print(f"[DEBUG] Key '{k}' not found in log for contains check.")
                                break
                        else:
                            result = expected_value.lower() in str(value).lower()
                            print(f"[DEBUG] [OR] Contains check: '{expected_value.lower()}' in log[{key_path}]='{value}'? {result}")
                            if result:
                                or_match = True
                                break
                    # Try regex
                    m_matches = re.match(r'\$(\w+(?:\.\w+)*)\s*matches\s*/(.+)/', sub)
                    if m_matches:
                        key_path, pattern = m_matches.groups()
                        keys = key_path.split('.')
                        value = log
                        for k in keys:
                            if isinstance(value, dict) and k in value:
                                value = value[k]
                            else:
                                print(f"[DEBUG] Key '{k}' not found in log for regex match.")
                                break
                        else:
                            try:
                                result = re.search(pattern, str(value), re.IGNORECASE) is not None
                            except re.error as e:
                                print(f"[DEBUG] Invalid regex pattern '{pattern}': {e}")
                                continue
                            print(f"[DEBUG] [OR] Regex match: log[{key_path}]='{value}' matches /{pattern}/? {result}")
                            if result:
                                or_match = True
                                break
                    # Try 'in' operator (OR logic)
                    m_in = re.match(r'\$(\w+(?:\.\w+)*)\s*in\s*\(([^)]+)\)', sub)
                    if m_in:
                        key_path, values_str = m_in.groups()
                        keys = key_path.split('.')
                        value = log
                        for k in keys:
                            if isinstance(value, dict) and k in value:
                                value = value[k]
                            else:
                                print(f"[DEBUG] Key '{k}' not found in log for 'in' check.")
                                break
                        else:
                            values = [v.strip().strip('"\'') for v in values_str.split(',')]
                            result = str(value) in values
                            print(f"[DEBUG] [OR] In check: log[{key_path}]='{value}' in {values}? {result}")
                            if result:
                                or_match = True
                                break
                if not or_match:
                    return False
                continue
            # --- Existing logic for single conditions ---
            # Equality
            m_eq = re.match(r'\$(\w+(?:\.\w+)*)\s*=\s*"([^"]+)"', event_line)
            if m_eq:
                key_path, expected_value = m_eq.groups()
                keys = key_path.split('.')
                value = log
                for k in keys:
                    if isinstance(value, dict) and k in value:
                        value = value[k]
                    else:
                        print(f"[DEBUG] Key '{k}' not found in log for equality check.")
                        return False
                result = str(value).lower() == expected_value.lower()
                print(f"[DEBUG] Equality check: log[{key_path}]='{value}' == '{expected_value}'? {result}")
                if not result:
                    return False
                continue
            # Contains
            m_contains = re.match(r'\$(\w+(?:\.\w+)*)\s*contains\s*"([^"]+)"', event_line)
            if m_contains:
                key_path, expected_value = m_contains.groups()
                keys = key_path.split('.')
                value = log
                for k in keys:
                    if isinstance(value, dict) and k in value:
                        value = value[k]
                    else:
                        print(f"[DEBUG] Key '{k}' not found in log for contains check.")
                        return False
                result = expected_value.lower() in str(value).lower()
                print(f"[DEBUG] Contains check: '{expected_value.lower()}' in log[{key_path}]='{value}'? {result}")
                if not result:
                    return False
                continue
            # Matches (regex)
            m_matches = re.match(r'\$(\w+(?:\.\w+)*)\s*matches\s*/(.+)/', event_line)
            if m_matches:
                key_path, pattern = m_matches.groups()
                keys = key_path.split('.')
                value = log
                for k in keys:
                    if isinstance(value, dict) and k in value:
                        value = value[k]
                    else:
                        print(f"[DEBUG] Key '{k}' not found in log for regex match.")
                        return False
                try:
                    result = re.search(pattern, str(value), re.IGNORECASE) is not None
                except re.error as e:
                    print(f"[DEBUG] Invalid regex pattern '{pattern}': {e}")
                    return False
                print(f"[DEBUG] Regex match: log[{key_path}]='{value}' matches /{pattern}/? {result}")
                if not result:
                    return False
                continue
            # 'in' operator (single condition)
            m_in = re.match(r'\$(\w+(?:\.\w+)*)\s*in\s*\(([^)]+)\)', event_line)
            if m_in:
                key_path, values_str = m_in.groups()
                keys = key_path.split('.')
                value = log
                for k in keys:
                    if isinstance(value, dict) and k in value:
                        value = value[k]
                    else:
                        print(f"[DEBUG] Key '{k}' not found in log for 'in' check.")
                        return False
                values = [v.strip().strip('"\'') for v in values_str.split(',')]
                result = str(value) in values
                print(f"[DEBUG] In check: log[{key_path}]='{value}' in {values}? {result}")
                if not result:
                    return False
                continue
            print(f"[DEBUG] Event line not recognized or unsupported: {event_line}")
            return False
        print(f"[DEBUG] Rule '{rule.get('meta', {}).get('description', 'unknown')}' matched log.")
        return True

    def reload(self):
        """Reload rules from disk."""
        self.rules = self._load_rules() 