#!/usr/bin/env python3
"""
AnikaLang Codebase Consolidator
Creates a single monolithic .py file from the entire codebase for AI analysis.
"""

import os
import sys
from datetime import datetime
from pathlib import Path

class CodebaseConsolidator:
    def __init__(self, base_dir="."):
        self.base_dir = Path(base_dir)
        self.output_file = "ANIKALANG_MONOLITHIC.py"
        self.files_processed = []
        self.total_lines = 0
        
    def collect_files(self):
        """Collect all .py files in the correct order."""
        files = []
        
        # 1. Main entry point
        main_py = self.base_dir / "main.py"
        if main_py.exists():
            files.append(main_py)
        
        # 2. Core modules (alphabetically)
        core_dir = self.base_dir / "core"
        if core_dir.exists():
            core_files = sorted(core_dir.glob("*.py"))
            files.extend(core_files)
        
        # 3. Plugin modules (alphabetically)
        plugins_dir = self.base_dir / "plugins"
        if plugins_dir.exists():
            plugin_files = sorted(plugins_dir.glob("*.py"))
            files.extend(plugin_files)
        
        return files
    
    def get_relative_path(self, filepath):
        """Get the relative path from base directory."""
        return str(filepath.relative_to(self.base_dir))
    
    def create_header(self):
        """Create the file header with metadata."""
        header = f'''#!/usr/bin/env python3
"""
================================================================================
ANIKALANG 1.2 - MONOLITHIC CODEBASE
================================================================================

Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Base Directory: {self.base_dir.absolute()}

This file contains the complete AnikaLang 1.2 codebase consolidated into a single
file for AI analysis and comprehension.

STRUCTURE:
- main.py: Application entry point
- core/: Core interpreter, lexer, parser, and utilities
- plugins/: Feature plugins (UI, database, AI, etc.)

TOTAL FILES: Will be updated after processing
TOTAL LINES: Will be updated after processing

================================================================================
"""

'''
        return header
    
    def create_file_section(self, filepath, content):
        """Create a section for a single file."""
        rel_path = self.get_relative_path(filepath)
        line_count = len(content.split('\n'))
        self.total_lines += line_count
        self.files_processed.append((rel_path, line_count))
        
        section = f'''
# ==============================================================================
# FILE: {rel_path}
# Lines: {line_count}
# ==============================================================================

{content}

'''
        return section
    
    def create_index(self):
        """Create a table of contents / index."""
        index = '''
# ==============================================================================
# TABLE OF CONTENTS
# ==============================================================================
'''
        for rel_path, line_count in self.files_processed:
            index += f'# - {rel_path} ({line_count} lines)\n'
        
        index += f'''
# Total Files: {len(self.files_processed)}
# Total Lines: {self.total_lines}
# ==============================================================================

'''
        return index
    
    def consolidate(self):
        """Main consolidation process."""
        print("🔍 Collecting files...")
        files = self.collect_files()
        
        if not files:
            print("❌ No .py files found!")
            return False
        
        print(f"✅ Found {len(files)} Python files")
        
        # Start building the monolithic file
        output_lines = []
        output_lines.append(self.create_header())
        
        # Add table of contents placeholder (will be updated later)
        toc_placeholder = len(output_lines)
        output_lines.append("# TABLE_OF_CONTENTS_PLACEHOLDER\n")
        
        # Process each file
        print("📝 Processing files...")
        for filepath in files:
            print(f"    {self.get_relative_path(filepath)}")
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                section = self.create_file_section(filepath, content)
                output_lines.append(section)
                
            except Exception as e:
                print(f"   ⚠️  Error reading {filepath}: {e}")
                error_section = f'''
# ==============================================================================
# FILE: {self.get_relative_path(filepath)}
# ERROR: Could not read file - {str(e)}
# ==============================================================================

'''
                output_lines.append(error_section)
        
        # Create final index
        index = self.create_index()
        
        # Replace placeholder with actual index
        output_content = '\n'.join(output_lines)
        output_content = output_content.replace('# TABLE_OF_CONTENTS_PLACEHOLDER\n', index)
        
        # Update header with final stats
        output_content = output_content.replace(
            'TOTAL FILES: Will be updated after processing',
            f'TOTAL FILES: {len(self.files_processed)}'
        )
        output_content = output_content.replace(
            'TOTAL LINES: Will be updated after processing',
            f'TOTAL LINES: {self.total_lines}'
        )
        
        # Write to output file
        output_path = self.base_dir / self.output_file
        print(f"\n💾 Writing to {output_path}...")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(output_content)
        
        print(f"\n✅ Success!")
        print(f"   Output: {output_path.absolute()}")
        print(f"   Files: {len(self.files_processed)}")
        print(f"   Total Lines: {self.total_lines}")
        print(f"   File Size: {output_path.stat().st_size / 1024:.1f} KB")
        
        return True

def main():
    """Main entry point."""
    # Get base directory from command line or use current directory
    base_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    
    print("=" * 70)
    print("ANIKALANG 1.2 CODEBASE CONSOLIDATOR")
    print("=" * 70)
    print()
    
    consolidator = CodebaseConsolidator(base_dir)
    success = consolidator.consolidate()
    
    if success:
        print("\n🎉 Monolithic file created successfully!")
        print("You can now feed this file to AI for analysis.")
    else:
        print("\n❌ Failed to create monolithic file.")
        sys.exit(1)

if __name__ == "__main__":
    main()