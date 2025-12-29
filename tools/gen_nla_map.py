#!/usr/bin/env python3
"""
Generate pyroute2 NLA mappings from Linux kernel header pkt_cls.h

This script reads /usr/include/linux/pkt_cls.h and generates Python code
for pyroute2 nla_map tuples, preserving the exact order from the kernel.

The kernel header comments are the source of truth for types.

Usage:
    python gen_nla_map.py [--header PATH] [--enum ENUM_PREFIX]

Examples:
    python gen_nla_map.py --enum TCA_FLOWER
    python gen_nla_map.py --enum TCA_U32
    python gen_nla_map.py --enum TCA_BPF
"""

import re
import argparse
import sys
from pathlib import Path

# Mapping from kernel type comments to pyroute2 NLA types
TYPE_MAPPINGS = {
    # From kernel comments - these are the source of truth
    'ETH_ALEN': 'l2addr',
    'be16': 'be16',
    'be32': 'be32',
    'u8': 'uint8',
    'u16': 'uint16',
    'u32': 'uint32',
    'u64': 'uint64',
    '__be16': 'be16',
    '__be32': 'be32',
    '__u8': 'uint8',
    '__u16': 'uint16',
    '__u32': 'uint32',
    '__u64': 'uint64',
    'struct in6_addr': 'ip6addr',
    'u128': 'hex',
}

# Name-based overrides that take precedence over kernel comments
# Use this for cases where pyroute2 needs a different type than the kernel specifies
NAME_OVERRIDES = [
    (r'_IPV4_[A-Z_]+$', 'ip4addr'),  # IPv4 addresses need ip4addr, not be32
]

# Fallback patterns for entries without kernel comments
NAME_PATTERN_MAPPINGS = [
    (r'_UNSPEC$', 'none'),
    (r'_ACT$', 'tca_act_prio'),
    (r'_INDEV$', 'asciiz'),
    (r'_NAME$', 'asciiz'),
    (r'_CLASSID$', 'uint32'),
    (r'_FLAGS$', 'uint32'),
    (r'_PAD$', 'hex'),
]

DEFAULT_TYPE = 'hex'


def parse_type_from_comment(comment):
    """Extract type from a kernel comment like /* be16 */ or /* ETH_ALEN */"""
    if not comment:
        return None

    # Clean up comment
    comment = comment.strip()
    if comment.startswith('/*'):
        comment = comment[2:]
    if comment.endswith('*/'):
        comment = comment[:-2]
    comment = comment.strip()

    # Try direct mapping
    if comment in TYPE_MAPPINGS:
        return TYPE_MAPPINGS[comment]

    # Try partial matches (e.g., "u8 - 8 bits" -> u8)
    for key, val in TYPE_MAPPINGS.items():
        if comment.startswith(key):
            return val

    return None


def infer_type_from_name(name):
    """Fallback: infer NLA type from name when no kernel comment exists"""
    for pattern, nla_type in NAME_PATTERN_MAPPINGS:
        if re.search(pattern, name):
            return nla_type
    return None


def get_nla_type(name, comment=None):
    """Determine NLA type - name overrides take precedence, then kernel comment"""
    # First: check name-based overrides (pyroute2-specific type requirements)
    for pattern, nla_type in NAME_OVERRIDES:
        if re.search(pattern, name):
            return nla_type

    # Second: use kernel comment if available
    if comment:
        type_from_comment = parse_type_from_comment(comment)
        if type_from_comment:
            return type_from_comment

    # Fallback: infer from name pattern
    type_from_name = infer_type_from_name(name)
    if type_from_name:
        return type_from_name

    return DEFAULT_TYPE


def parse_enum(content, enum_prefix):
    """
    Parse an enum from the header content.
    Returns list of (name, type, comment) tuples in order.
    """
    max_marker = f'__{enum_prefix}_MAX'

    # Find all enum blocks
    enum_pattern = r'enum\s*(?:\w+)?\s*\{\s*([^}]+)\}'
    matches = list(re.finditer(enum_pattern, content, re.DOTALL))

    if not matches:
        print(f"Error: Could not find any enums in header", file=sys.stderr)
        return []

    # Find the enum with PREFIX_UNSPEC and __PREFIX_MAX
    target_enum = None
    for match in matches:
        enum_body = match.group(1)
        if f'{enum_prefix}_UNSPEC' in enum_body and max_marker in enum_body:
            entry_count = len(re.findall(rf'{enum_prefix}_\w+', enum_body))
            if target_enum is None or entry_count > len(re.findall(rf'{enum_prefix}_\w+', target_enum)):
                target_enum = enum_body

    if target_enum is None:
        print(f"Error: Could not find enum with prefix '{enum_prefix}'",
              file=sys.stderr)
        return []

    results = []

    # Parse each entry: NAME, or NAME = value, with optional /* comment */
    line_pattern = rf'({enum_prefix}_[A-Z0-9_]+)\s*(?:=\s*[^,\n]+)?,?\s*(/\*[^*]*\*/)?'

    for line_match in re.finditer(line_pattern, target_enum):
        name = line_match.group(1)
        comment = line_match.group(2)

        # Skip __PREFIX entries
        if name.startswith('__'):
            continue

        # Skip bounds markers (PREFIX_MAX) but keep KEY_*_MAX (port ranges)
        if name.endswith('_MAX') and '_KEY_' not in name:
            continue

        nla_type = get_nla_type(name, comment)
        results.append((name, nla_type, comment))

    return results


def generate_nla_map(entries, class_name='options', indent=4, show_comments=True):
    """Generate Python code for the nla_map class"""
    lines = []
    lines.append(f"class {class_name}(nla):")
    lines.append(f"{' ' * indent}nla_map = (")

    for name, nla_type, comment in entries:
        comment_str = f"  # {comment}" if (comment and show_comments) else ""
        lines.append(f"{' ' * (indent * 2)}('{name}', '{nla_type}'),{comment_str}")

    lines.append(f"{' ' * indent})")

    return '\n'.join(lines)


def generate_nla_map_tuple_only(entries, show_comments=True):
    """Generate just the nla_map tuple"""
    lines = []
    lines.append("    nla_map = (")

    for name, nla_type, comment in entries:
        comment_str = f"  # {comment}" if (comment and show_comments) else ""
        lines.append(f"        ('{name}', '{nla_type}'),{comment_str}")

    lines.append("    )")

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='Generate pyroute2 NLA mappings from kernel headers'
    )
    parser.add_argument(
        '--header', '-H',
        default='/usr/include/linux/pkt_cls.h',
        help='Path to pkt_cls.h header file'
    )
    parser.add_argument(
        '--enum', '-e',
        default='TCA_FLOWER',
        help='Enum prefix to parse (e.g., TCA_FLOWER, TCA_U32, TCA_BPF)'
    )
    parser.add_argument(
        '--class-name', '-c',
        default='options',
        help='Name for the generated class'
    )
    parser.add_argument(
        '--tuple-only', '-t',
        action='store_true',
        help='Output only the nla_map tuple (no class wrapper)'
    )
    parser.add_argument(
        '--list-enums', '-l',
        action='store_true',
        help='List all TCA_* enum prefixes found in the header'
    )
    parser.add_argument(
        '--no-comments',
        action='store_true',
        help='Do not include kernel type comments in output'
    )

    args = parser.parse_args()

    # Read header file
    header_path = Path(args.header)
    if not header_path.exists():
        print(f"Error: Header file not found: {header_path}", file=sys.stderr)
        sys.exit(1)

    content = header_path.read_text()

    if args.list_enums:
        prefixes = set()
        for match in re.finditer(r'\b(TCA_\w+?)_', content):
            prefix = match.group(1)
            if not prefix.startswith('TCA_ACT_') or prefix == 'TCA_ACT':
                prefixes.add(prefix)

        print("Found enum prefixes:")
        for prefix in sorted(prefixes):
            print(f"  {prefix}")
        return

    # Parse the enum
    entries = parse_enum(content, args.enum)

    if not entries:
        print(f"No entries found for prefix '{args.enum}'", file=sys.stderr)
        sys.exit(1)

    print(f"# Generated from {args.header}")
    print(f"# Enum prefix: {args.enum}")
    print(f"# Found {len(entries)} entries")
    print()

    show_comments = not args.no_comments
    if args.tuple_only:
        print(generate_nla_map_tuple_only(entries, show_comments))
    else:
        print(generate_nla_map(entries, args.class_name, show_comments=show_comments))


if __name__ == '__main__':
    main()
